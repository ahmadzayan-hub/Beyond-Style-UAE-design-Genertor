"use client";

import { useState } from "react";
import { Lang, STRINGS } from "@/lib/i18n";
import type { Strings } from "./types";
import { Button, Card, Checkbox, Input } from "@/components/ui";

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
    <section className="flex flex-col gap-5 animate-fade-up">
      <div>
        <h2 className="font-display text-2xl text-ink-900">{t.approve_title}</h2>
        <p className="mt-1 text-xs text-ink-500">{t.agreement_note}</p>
      </div>
      <Card padding="md" className="proof-svg-large" data-testid="agreement-proof">
        {(agreementSvg ?? selected.svg) && (
          <div dangerouslySetInnerHTML={{ __html: agreementSvg ?? selected.svg ?? "" }} />
        )}
      </Card>
      <div
        data-testid="approve-text-display"
        dir="auto"
        className="surface-paper rounded-3xl border-2 border-gold-400 bg-white p-6 text-center font-display text-3xl text-ink-900 shadow-soft whitespace-pre-line sm:text-4xl"
      >
        {normalizedText}
      </div>
      <Card title={t.link_title} subtitle={t.link_note} data-testid="secure-link-box">
        {!link ? (
          <Button variant="secondary" size="sm" data-testid="create-approval-link" disabled={busy} onClick={onCreateLink}>
            {t.link_create}
          </Button>
        ) : (
          <div className="flex flex-col gap-2">
            <Input readOnly dir="ltr" value={link.url} data-testid="approval-link-url" className="font-mono text-xs" onFocus={(e) => e.currentTarget.select()} />
            <p className="text-[11px] text-ink-500">{t.link_expires}: {new Date(link.expires_at).toLocaleString()}</p>
            <div className="flex gap-2">
              <Button
                variant="secondary" size="sm" className="flex-1"
                data-testid="copy-approval-link"
                onClick={async () => {
                  try { await navigator.clipboard.writeText(link.url); setCopied(true); } catch { setCopied(false); }
                }}
              >
                {copied ? t.link_copied : t.link_copy}
              </Button>
              <a
                data-testid="whatsapp-approval-link"
                href={`https://wa.me/?text=${encodeURIComponent(link.url)}`}
                target="_blank" rel="noreferrer"
                className="inline-flex h-9 flex-1 items-center justify-center rounded-lg bg-ok-600 px-3 text-sm font-semibold text-white hover:bg-ok-800"
              >
                {t.link_whatsapp}
              </a>
            </div>
          </div>
        )}
        <p className="mt-3 text-xs text-ink-500">{t.link_or_internal}</p>
      </Card>
      <Card tone="gold" padding="sm">
        <Checkbox
          data-testid="approve-checkbox"
          checked={approveChecked}
          onChange={(e) => setApproveChecked(e.target.checked)}
          label={
            <>
              {t.approve_statement}
              <span className="mt-1 block text-xs font-normal text-ink-500">
                {lang === "ar" ? STRINGS.en.approve_statement : STRINGS.ar.approve_statement}
              </span>
            </>
          }
        />
      </Card>
      <Button size="lg" block variant="gold" data-testid="approve-button" disabled={!approveChecked || busy} loading={busy} onClick={onApprove}>
        {t.approve_btn}
      </Button>
      <Button variant="ghost" size="sm" onClick={onBack} className="self-center">
        {t.back}
      </Button>
    </section>
  );
}
