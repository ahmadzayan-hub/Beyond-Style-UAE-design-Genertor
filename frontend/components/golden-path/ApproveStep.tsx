"use client";

import { useState } from "react";
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
  /** Secure customer link (single-use, expiring). `link` is null until minted. */
  link: { url: string; expires_at: string } | null;
  onCreateLink: () => void;
}

export default function ApproveStep({
  t, lang, agreementSvg, selected, normalizedText, approveChecked, setApproveChecked,
  busy, onApprove, onBack, link, onCreateLink,
}: ApproveStepProps) {
  const [copied, setCopied] = useState(false);
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
      <div className="rounded-xl border border-stone-200 bg-white p-4" data-testid="secure-link-box">
        <p className="text-sm font-bold">{t.link_title}</p>
        <p className="mt-1 text-[11px] text-stone-500">{t.link_note}</p>
        {!link ? (
          <button
            data-testid="create-approval-link"
            disabled={busy}
            onClick={onCreateLink}
            className="mt-3 rounded-lg border border-brand-gold px-4 py-2 text-sm font-semibold text-brand-gold disabled:opacity-40"
          >
            {t.link_create}
          </button>
        ) : (
          <div className="mt-3 flex flex-col gap-2">
            <input readOnly dir="ltr" value={link.url} data-testid="approval-link-url"
                   className="w-full rounded border border-stone-300 p-2 text-xs" onFocus={(e) => e.currentTarget.select()} />
            <p className="text-[11px] text-stone-500">{t.link_expires}: {new Date(link.expires_at).toLocaleString()}</p>
            <div className="flex gap-2">
              <button
                data-testid="copy-approval-link"
                onClick={async () => {
                  try { await navigator.clipboard.writeText(link.url); setCopied(true); } catch { setCopied(false); }
                }}
                className="flex-1 rounded-lg border border-stone-300 py-2 text-sm"
              >
                {copied ? t.link_copied : t.link_copy}
              </button>
              <a
                data-testid="whatsapp-approval-link"
                href={`https://wa.me/?text=${encodeURIComponent(link.url)}`}
                target="_blank" rel="noreferrer"
                className="flex-1 rounded-lg bg-emerald-700 py-2 text-center text-sm font-semibold text-white"
              >
                {t.link_whatsapp}
              </a>
            </div>
          </div>
        )}
      </div>
      <p className="text-xs text-stone-500">{t.link_or_internal}</p>
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
