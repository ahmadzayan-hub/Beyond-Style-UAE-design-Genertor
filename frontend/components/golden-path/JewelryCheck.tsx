"use client";

import type { Strings } from "./types";

export interface QaReport {
  status: "PASS" | "FAIL";
  label: string;
  summary_en: string;
  summary_ar: string;
  errors: { code: string; explanation_en: string; explanation_ar: string; detail: string }[];
  warnings: { code: string; explanation_en: string; explanation_ar: string; detail: string }[];
  attachment: { mode: string; expected_rings: number; real_geometry: boolean; note_en: string; note_ar: string };
  weight: null | {
    material: { label_en: string; label_ar: string; workshop_ready: boolean };
    thickness_mm: number; metal_area_mm2: number; volume_mm3: number; estimated_weight_g: number;
    warnings: { code: string; en: string; ar: string }[];
    target?: { target_weight_g: number; deviation_pct: number; within_tolerance: boolean; thickness_for_target_mm: number | null };
  };
}

/** Step 7 — Jewelry Check: the manufacturing gate in plain language plus
 * the geometry-based weight. Deterministic; never an AI opinion. */
export default function JewelryCheck({ t, lang, report, thickness, setThickness }: {
  t: Strings; lang: "ar" | "en"; report: QaReport; thickness: number; setThickness: (v: number) => void;
}) {
  const pass = report.status === "PASS";
  const ar = lang === "ar";
  return (
    <div className="rounded-xl border border-stone-200 bg-white p-4" data-testid="jewelry-check">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold">{t.jewelry_check_title}</p>
        <span data-testid="jewelry-qa-label" className={`rounded-full px-3 py-1 text-xs font-bold ${pass ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`}>
          {pass ? t.jewelry_pass : t.jewelry_fail}
        </span>
      </div>
      <p className="mt-2 text-xs text-stone-600">{ar ? report.summary_ar : report.summary_en}</p>
      {report.errors.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-red-700" data-testid="jewelry-qa-errors">
          {report.errors.map((e, k) => <li key={k}>• {ar ? e.explanation_ar : e.explanation_en}</li>)}
        </ul>
      )}
      {report.warnings.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-amber-700">
          {report.warnings.map((e, k) => <li key={k}>• {ar ? e.explanation_ar : e.explanation_en}</li>)}
        </ul>
      )}
      <p className="mt-2 text-[11px] text-stone-500">{ar ? report.attachment.note_ar : report.attachment.note_en}</p>
      {report.weight && (
        <div className="mt-3 rounded-lg bg-stone-50 p-3 text-xs" data-testid="weight-report">
          <div className="flex items-center justify-between">
            <span className="font-semibold">{t.weight_title}</span>
            <label className="flex items-center gap-2">
              {t.thickness_label}
              <select value={thickness} onChange={(e) => setThickness(Number(e.target.value))} data-testid="thickness-select"
                      className="rounded border border-stone-300 p-1">
                {[0.8, 1.0, 1.2, 1.5, 2.0].map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </label>
          </div>
          <p className="mt-1 text-lg font-bold" data-testid="weight-value">{report.weight.estimated_weight_g} g</p>
          <p className="text-[11px] text-stone-500">
            {ar ? report.weight.material.label_ar : report.weight.material.label_en} · {report.weight.metal_area_mm2} mm² · {report.weight.volume_mm3} mm³ · {t.weight_basis}
          </p>
          {report.weight.warnings.map((w, k) => <p key={k} className="mt-1 text-[11px] text-amber-700">{ar ? w.ar : w.en}</p>)}
        </div>
      )}
    </div>
  );
}
