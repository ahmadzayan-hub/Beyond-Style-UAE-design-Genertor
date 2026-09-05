"use client";

import type { Strings } from "./types";

export interface Ladder {
  current_state: string;
  current_label_ar: string;
  rungs: { state: string; label_ar: string; reached: boolean; reason_en: string; reason_ar: string }[];
  approval_channel_note: string;
}

/** Readiness derived from recorded facts (text, QA, approval, export
 * fidelity, workshop order). */
export default function ReadinessLadder({ t, lang, ladder }: { t: Strings; lang: "ar" | "en"; ladder: Ladder }) {
  const ar = lang === "ar";
  return (
    <div className="rounded-xl border border-stone-200 bg-white p-4" data-testid="readiness-ladder">
      <p className="text-sm font-semibold">{t.readiness_title}: <span data-testid="readiness-state">{ar ? ladder.current_label_ar : ladder.current_state.replace(/_/g, " ")}</span></p>
      <ol className="mt-2 space-y-1 text-xs">
        {ladder.rungs.map((r) => (
          <li key={r.state} className={r.reached ? "text-emerald-800" : "text-stone-400"} data-testid={`rung-${r.state}`}>
            {r.reached ? "●" : "○"} {ar ? r.label_ar : r.state.replace(/_/g, " ")} — {ar ? r.reason_ar : r.reason_en}
          </li>
        ))}
      </ol>
    </div>
  );
}
