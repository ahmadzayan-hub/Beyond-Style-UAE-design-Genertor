"use client";

import type { Strings } from "./types";

export interface IntegrityReport {
  status: "PASS" | "FAIL";
  label: string;
  normalized_text: string;
  sha256_normalized: string;
  characters: { index: number; char: string; codepoint: string; name: string; category: string }[];
  issues: { code: string; severity: string; index: number | null; detail: string; detail_ar: string }[];
  suggested_clean_text: string | null;
}

/** Verify-Spelling step: every character as entered, hidden-character
 * findings in plain language, and the TEXT INTEGRITY verdict. Never
 * auto-corrects. */
export default function IntegrityPanel({ t, lang, report }: { t: Strings; lang: "ar" | "en"; report: IntegrityReport }) {
  const pass = report.status === "PASS";
  return (
    <div className="rounded-xl border border-stone-200 bg-white p-4" data-testid="integrity-panel">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold">{t.integrity_title}</p>
        <span
          data-testid="integrity-label"
          className={`rounded-full px-3 py-1 text-xs font-bold ${pass ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`}
        >
          {pass ? t.integrity_pass : t.integrity_fail}
        </span>
      </div>
      <p className="mt-2 text-[11px] text-stone-500">{t.integrity_chars}</p>
      <div className="mt-1 flex flex-wrap gap-1" dir="rtl" data-testid="integrity-chars">
        {report.characters.map((c) => (
          <span
            key={c.index}
            title={`${c.codepoint} ${c.name}`}
            className={`rounded border px-2 py-1 text-lg ${c.category.startsWith("C") || c.category === "Cf" ? "border-red-300 bg-red-50" : "border-stone-200"}`}
          >
            {c.char.trim() ? c.char : "␣"}
          </span>
        ))}
      </div>
      {report.issues.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs" data-testid="integrity-issues">
          {report.issues.map((i, k) => (
            <li key={k} className={i.severity === "ERROR" ? "text-red-700" : "text-amber-700"}>
              {lang === "ar" ? i.detail_ar : i.detail}
            </li>
          ))}
        </ul>
      )}
      {!pass && <p className="mt-2 text-xs font-medium text-red-700">{t.integrity_hidden}</p>}
      <p className="mt-2 break-all text-[10px] text-stone-400">SHA-256 {report.sha256_normalized}</p>
    </div>
  );
}
