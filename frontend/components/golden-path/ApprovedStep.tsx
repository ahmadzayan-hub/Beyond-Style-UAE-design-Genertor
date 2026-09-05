"use client";

import ReadinessLadder, { Ladder } from "./ReadinessLadder";
import type { Strings } from "./types";

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
    <section className="flex flex-col gap-5" data-testid="approved">
      <h2 className="text-2xl font-bold text-emerald-700">{t.approved_title}</h2>
      <div className="proof-svg-large rounded-xl border border-stone-200 bg-white p-4">
        {selected.svg && <div dangerouslySetInnerHTML={{ __html: selected.svg }} />}
      </div>
      <div className="rounded-lg bg-white p-4 text-sm">
        <p>
          {t.approved_version}: <b data-testid="locked-version">{selected.version_number}</b>
        </p>
        <p className="mt-1 break-all text-[10px] text-stone-400" data-testid="approval-hash">
          {approval.approval_hash}
        </p>
        <p className="mt-2 text-[11px] text-stone-500">{t.approval_internal_note}</p>
      </div>
      {Object.keys(fidelity).length > 0 && (
        <div className="flex flex-wrap gap-2 text-xs" data-testid="fidelity-badges">
          {Object.entries(fidelity).map(([fmt, status]) => (
            <span key={fmt} data-testid={`fidelity-${fmt}`}
                  className={`rounded-full px-3 py-1 font-semibold ${status === "PASS" ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`}>
              {fmt.toUpperCase()} · {status === "PASS" ? t.fidelity_pass : t.fidelity_fail}
            </span>
          ))}
        </div>
      )}
      <p className="text-[11px] text-stone-500">{t.fidelity_note}</p>
      {ladder && <ReadinessLadder t={t} lang={lang} ladder={ladder} />}
      <p data-testid="workshop-ready" className={`text-sm font-bold ${workshopReady ? "text-emerald-700" : "text-stone-500"}`}>
        {workshopReady ? t.workshop_ready : t.not_workshop_ready}
      </p>
      <div className="flex gap-3">
        <button
          data-testid="download-svg"
          onClick={() => onDownload("svg")}
          className="flex-1 rounded-xl border border-brand-gold p-3 font-semibold text-brand-gold"
        >
          {t.download_svg}
        </button>
        <button
          data-testid="download-dxf"
          onClick={() => onDownload("dxf")}
          className="flex-1 rounded-xl bg-brand-gold p-3 font-semibold text-white"
        >
          {t.download_dxf}
        </button>
      </div>
      <button
        data-testid="download-pdf"
        onClick={() => onDownload("pdf")}
        className="rounded-xl border border-brand-gold p-3 font-semibold text-brand-gold"
      >
        {t.download_pdf}
      </button>
      <button
        data-testid="download-png"
        onClick={() => onDownload("png")}
        className="rounded-xl border border-brand-gold p-3 font-semibold text-brand-gold"
      >
        {t.download_png}
      </button>
      <button
        disabled
        title="coming soon"
        data-testid="make-it-disabled"
        className="rounded-xl bg-stone-300 p-4 text-lg font-semibold text-stone-500"
      >
        {t.make_it}
      </button>
    </section>
  );
}
