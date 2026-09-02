"use client";

import type { Strings } from "./types";

/** Locked version: hash, workshop downloads. The "make it" button stays
 * honestly disabled — customer ordering is not built. */
export interface ApprovedStepProps {
  t: Strings;
  selected: { svg?: string; version_number: number };
  approval: { approval_hash: string };
  onDownload: (fmt: "svg" | "dxf") => void;
}

export default function ApprovedStep({ t, selected, approval, onDownload }: ApprovedStepProps) {
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
      </div>
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
