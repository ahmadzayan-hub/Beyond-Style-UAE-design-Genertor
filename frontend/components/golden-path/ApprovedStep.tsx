"use client";

import ReadinessLadder, { Ladder } from "./ReadinessLadder";
import type { Strings } from "./types";
import { Badge, Button, Card } from "@/components/ui";

/** Locked version: hash, workshop downloads. The "make it" button stays
 * honestly disabled — customer ordering is not built. */
export interface ApprovedStepProps {
  t: Strings;
  selected: { svg?: string; version_number: number };
  approval: { approval_hash: string };
  onDownload: (fmt: "svg" | "dxf" | "pdf" | "png") => void;
  lang: "ar" | "en";
  fidelity: Record<string, string>;
  ladder: Ladder | null;
}

export default function ApprovedStep({ t, selected, approval, onDownload, lang, fidelity, ladder }: ApprovedStepProps) {
  const workshopReady = ladder?.rungs.find((r) => r.state === "WORKSHOP_READY")?.reached;
  return (
    <section className="flex flex-col gap-5 animate-fade-up" data-testid="approved">
      <div className="flex items-center gap-3">
        <span aria-hidden className="flex h-10 w-10 items-center justify-center rounded-full bg-ok-50 text-lg text-ok-800">✓</span>
        <h2 className="font-display text-2xl text-ok-800">{t.approved_title}</h2>
      </div>
      <Card className="proof-svg-large">
        {selected.svg && <div dangerouslySetInnerHTML={{ __html: selected.svg }} />}
      </Card>
      <Card padding="sm" tone="muted">
        <p className="text-sm text-ink-800">
          {t.approved_version}: <b data-testid="locked-version">{selected.version_number}</b>
        </p>
        <p className="mt-1 break-all font-mono text-[10px] text-ink-400" data-testid="approval-hash">
          {approval.approval_hash}
        </p>
        <p className="mt-2 text-[11px] text-ink-500">{t.approval_internal_note}</p>
      </Card>
      {Object.keys(fidelity).length > 0 && (
        <div className="flex flex-wrap gap-2" data-testid="fidelity-badges">
          {Object.entries(fidelity).map(([fmt, status]) => (
            <Badge key={fmt} data-testid={`fidelity-${fmt}`} tone={status === "PASS" ? "ok" : "danger"}>
              {fmt.toUpperCase()} · {status === "PASS" ? t.fidelity_pass : t.fidelity_fail}
            </Badge>
          ))}
        </div>
      )}
      <p className="text-[11px] text-ink-500">{t.fidelity_note}</p>
      {ladder && <ReadinessLadder t={t} lang={lang} ladder={ladder} />}
      <p data-testid="workshop-ready" className={`text-sm font-bold ${workshopReady ? "text-ok-800" : "text-ink-500"}`}>
        {workshopReady ? t.workshop_ready : t.not_workshop_ready}
      </p>
      <div className="grid grid-cols-2 gap-3">
        <Button variant="secondary" data-testid="download-svg" onClick={() => onDownload("svg")}>{t.download_svg}</Button>
        <Button variant="gold" data-testid="download-dxf" onClick={() => onDownload("dxf")}>{t.download_dxf}</Button>
        <Button variant="secondary" data-testid="download-pdf" onClick={() => onDownload("pdf")}>{t.download_pdf}</Button>
        <Button variant="secondary" data-testid="download-png" onClick={() => onDownload("png")}>{t.download_png}</Button>
      </div>
      <Button size="lg" block disabled title="coming soon" data-testid="make-it-disabled" className="bg-cream-300 text-ink-500">
        {t.make_it}
      </Button>
    </section>
  );
}
