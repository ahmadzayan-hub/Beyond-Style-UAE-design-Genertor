"use client";

import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { VectorOp } from "@/lib/api";
import type { Lang } from "@/lib/i18n";
import type { Strings } from "./types";

interface Catalogue {
  editable: boolean;
  bounds_mm: number[] | null;
  workshop_minimums: Record<string, number>;
  tools: { op: string; label_ar: string; label_en: string }[];
  refused: { op: string; label_ar: string; label_en: string; reason_ar: string; reason_en: string }[];
  lineage_ops: VectorOp[];
  proposed_fix_ops: Record<string, VectorOp[]>;
  errors: { code: string; detail: string }[];
}

interface Preview {
  svg: string;
  validation_passed: boolean;
  violations: { code: string; detail: string }[];
}

const RING_POSITIONS = ["top_center", "top_left", "top_right", "left", "right", "bottom_center"];

/** Pro mode: real vector operations on the selected version. Every op is
 *  previewed server-side with the same fail-safes, then applied as a NEW
 *  version. Refused/unbuilt tools are listed with the reason — never as
 *  clickable fakes. */
export default function ProPanel({
  t, lang, versionId, currentSvg, busy, onApplied, onError,
}: {
  t: Strings; lang: Lang; versionId: string; currentSvg?: string; busy: boolean;
  onApplied: (res: any) => Promise<void>; onError: (msg: string) => void;
}) {
  const [cat, setCat] = useState<Catalogue | null>(null);
  const [pending, setPending] = useState<VectorOp[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [rejected, setRejected] = useState<string | null>(null);
  const [ringPos, setRingPos] = useState("top_center");
  const [circle, setCircle] = useState({ x: 0, y: 0, d: 2 });
  const [working, setWorking] = useState(false);

  useEffect(() => {
    let alive = true;
    setPending([]); setPreview(null); setRejected(null);
    api.vectorOps(versionId).then((c) => {
      if (!alive) return;
      setCat(c);
      if (c.bounds_mm) {
        const [x0, y0, x1, y1] = c.bounds_mm;
        setCircle({ x: Number(((x0 + x1) / 2).toFixed(1)), y: Number((y1 + 1).toFixed(1)), d: 2 });
      }
    }).catch((e) => onError(String(e?.message ?? e)));
    return () => { alive = false; };
  }, [versionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const L = (o: { label_ar: string; label_en: string }) => (lang === "ar" ? o.label_ar : o.label_en);
  const add = (op: VectorOp) => { setPending((p) => [...p, op]); setPreview(null); setRejected(null); };

  async function doPreview() {
    if (!pending.length) return;
    setWorking(true); setRejected(null);
    try {
      setPreview(await api.vectorEditPreview(versionId, pending));
    } catch (e: any) {
      setRejected(e?.message ?? String(e));
      setPreview(null);
    } finally { setWorking(false); }
  }

  async function doApply() {
    if (!pending.length) return;
    setWorking(true); setRejected(null);
    try {
      const res = await api.vectorEdit(versionId, pending, "pro mode");
      await onApplied(res);
    } catch (e: any) {
      setRejected(e?.message ?? String(e));
    } finally { setWorking(false); }
  }

  if (!cat) return <p className="text-xs text-stone-500" data-testid="pro-loading">…</p>;
  const dis = busy || working || !cat.editable;
  const btn = "rounded border border-stone-300 bg-white px-2 py-1 text-xs disabled:opacity-40";

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-stone-200 bg-white p-4" data-testid="pro-panel">
      <p className="text-sm font-bold">{t.pro_title}</p>
      <p className="text-[11px] text-stone-500">{t.pro_note}</p>
      {cat.bounds_mm && (
        <p className="text-[11px] text-stone-500" data-testid="pro-bounds">
          {t.pro_bounds}: {cat.bounds_mm.map((b) => b.toFixed(1)).join(" · ")}
        </p>
      )}

      <div className="flex flex-wrap gap-1" data-testid="pro-transforms">
        <span className="w-full text-xs font-semibold">{t.pro_move}</span>
        {([["←", -1, 0], ["→", 1, 0], ["↑", 0, 1], ["↓", 0, -1]] as [string, number, number][]).map(([g, dx, dy]) => (
          <button key={g} className={btn} disabled={dis} data-testid={`pro-move-${dx}-${dy}`}
                  onClick={() => add({ op: "translate", params: { dx_mm: dx, dy_mm: dy } })}>{g}</button>
        ))}
        <span className="w-full text-xs font-semibold">{t.pro_rotate}</span>
        <button className={btn} disabled={dis} data-testid="pro-rotate-ccw" onClick={() => add({ op: "rotate", params: { angle_deg: 5 } })}>↺ 5°</button>
        <button className={btn} disabled={dis} data-testid="pro-rotate-cw" onClick={() => add({ op: "rotate", params: { angle_deg: -5 } })}>↻ 5°</button>
        <span className="w-full text-xs font-semibold">{t.pro_scale}</span>
        <button className={btn} disabled={dis} data-testid="pro-scale-down" onClick={() => add({ op: "scale", params: { factor: 0.95 } })}>− 5%</button>
        <button className={btn} disabled={dis} data-testid="pro-scale-up" onClick={() => add({ op: "scale", params: { factor: 1.05 } })}>+ 5%</button>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs">
          {t.pro_ring_pos}
          <select value={ringPos} onChange={(e) => setRingPos(e.target.value)} data-testid="pro-ring-pos"
                  className="mt-1 block rounded border border-stone-300 p-1">
            {RING_POSITIONS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <button className={btn} disabled={dis} data-testid="pro-add-ring"
                onClick={() => add({ op: "add_ring", params: { position: ringPos } })}>{t.pro_ring}</button>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        {(["x", "y", "d"] as const).map((k) => (
          <label key={k} className="text-xs">
            {k === "x" ? t.pro_center_x : k === "y" ? t.pro_center_y : t.pro_diameter}
            <input type="number" step="0.1" value={circle[k]} data-testid={`pro-circle-${k}`}
                   onChange={(e) => setCircle({ ...circle, [k]: Number(e.target.value) })}
                   className="mt-1 block w-24 rounded border border-stone-300 p-1" />
          </label>
        ))}
        <button className={btn} disabled={dis} data-testid="pro-cut-circle"
                onClick={() => add({ op: "cut_shape", params: { shape: "circle", center: [circle.x, circle.y], diameter_mm: circle.d } })}>{t.pro_cut}</button>
        <button className={btn} disabled={dis} data-testid="pro-union-circle"
                onClick={() => add({ op: "add_shape", params: { shape: "circle", center: [circle.x, circle.y], diameter_mm: circle.d } })}>{t.pro_union}</button>
      </div>

      {Object.keys(cat.proposed_fix_ops).length > 0 && (
        <div className="rounded-lg bg-emerald-50 p-2" data-testid="pro-fix-ops">
          <p className="text-xs font-semibold text-emerald-900">{t.pro_fix_ops}</p>
          {Object.entries(cat.proposed_fix_ops).map(([id, ops]) => (
            <button key={id} className={`${btn} mt-1 me-1`} disabled={dis} data-testid={`pro-fix-${id}`}
                    onClick={() => ops.forEach(add)}>{id} ({ops.length})</button>
          ))}
        </div>
      )}

      {pending.length > 0 && (
        <div data-testid="pro-pending">
          <p className="text-xs font-semibold">{t.pro_pending} ({pending.length})</p>
          <ol className="mt-1 flex flex-col gap-1 text-[11px]">
            {pending.map((op, i) => (
              <li key={i} className="flex items-center justify-between rounded bg-stone-50 px-2 py-1">
                <code dir="ltr">{op.op} {JSON.stringify(op.params)}</code>
                <button className="text-red-700" onClick={() => setPending(pending.filter((_, j) => j !== i))} aria-label="remove">✕</button>
              </li>
            ))}
          </ol>
          <div className="mt-2 flex gap-2">
            <button className="flex-1 rounded-lg border border-brand-gold py-2 text-sm font-semibold text-brand-gold disabled:opacity-40"
                    disabled={dis} data-testid="pro-preview" onClick={doPreview}>{t.pro_preview}</button>
            <button className="flex-1 rounded-lg bg-brand-dark py-2 text-sm font-semibold text-white disabled:opacity-40"
                    disabled={dis} data-testid="pro-apply" onClick={doApply}>{t.pro_apply}</button>
            <button className={btn} onClick={() => { setPending([]); setPreview(null); setRejected(null); }}>{t.pro_clear}</button>
          </div>
        </div>
      )}

      {rejected && (
        <p className="rounded-lg border border-red-300 bg-red-50 p-2 text-xs text-red-800" data-testid="pro-rejected">
          {t.pro_rejected} {rejected}
        </p>
      )}

      {preview && (
        <div data-testid="pro-preview-result">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-xs text-stone-500">{t.before}</p>
              {currentSvg && <div className="proof-svg rounded bg-white p-2" dangerouslySetInnerHTML={{ __html: currentSvg }} />}
            </div>
            <div>
              <p className="text-xs text-stone-500">{t.after}</p>
              <div className="proof-svg rounded bg-white p-2" dangerouslySetInnerHTML={{ __html: preview.svg }} />
            </div>
          </div>
          <p className="mt-1 text-xs" data-testid="pro-errors-after">
            {t.pro_errors_after}: {preview.violations.length ? preview.violations.map((v) => v.code).join(", ") : t.pro_none}
          </p>
        </div>
      )}

      <div className="text-[11px] text-stone-500" data-testid="pro-refused">
        <p className="font-semibold">{t.pro_refused}</p>
        <ul className="mt-1 flex flex-col gap-0.5">
          {cat.refused.map((r) => (
            <li key={r.op}><span className="line-through">{L(r)}</span> — {lang === "ar" ? r.reason_ar : r.reason_en}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
