"use client";

// Internal Art Director screen. The reviewer judges a rendered jewellery
// piece, not a font specimen: the proof is the largest thing on the card,
// the customer-facing style word is the label, and the OpenType/axis detail
// sits in a collapsed technical block.
//
// Nothing here decides anything. An item with no human review shows
// HUMAN_REVIEW_PENDING, and the software never fills that in.

import { useCallback, useEffect, useMemo, useState } from "react";
import * as api from "@/lib/api";

type Decision = "APPROVE" | "ALLOW" | "EXPERIMENTAL" | "HIDE";

interface Engineering {
  arabic_identity_pass: boolean;
  manufacturing_pass: boolean;
  rights_pass: boolean;
  min_material_width_mm: number | null;
  min_gap_mm: number | null;
  counter_clearance_mm: number | null;
  mm_failures: string[];
}

interface ReviewItem {
  item_id: string;
  recipe_hash: string;
  product: string;
  font_family: string;
  customer_style: string | null;
  source_text: string;
  composition: string;
  width_mm: number;
  height_mm: number;
  manufacturing_pass: boolean;
  golden_production_pattern: string[];
  proof_path_d: string;
  proof_view: [number, number];
  technical: { font_id: string; feature_set: string; font_axes: Record<string, number> };
  engineering: Engineering;
  // Prior reviewers' opinions are withheld while blinded, so these are optional.
  curation: {
    state: string; reason: string; human_review_status: string; failed_gates: string[];
    human_decision?: string | null; reviewer?: string;
  };
}

const DECISIONS: Decision[] = ["APPROVE", "ALLOW", "EXPERIMENTAL", "HIDE"];

function Proof({ item }: { item: ReviewItem }) {
  const [w, h] = item.proof_view;
  const pad = Math.max(w, h) * 0.06;
  return (
    <svg
      viewBox={`${-pad} ${-pad} ${w + pad * 2} ${h + pad * 2}`}
      className="w-full h-64 bg-white"
      role="img"
      aria-label={`${item.font_family} ${item.source_text}`}
    >
      <path d={item.proof_path_d} fill="#111" fillRule="evenodd" />
    </svg>
  );
}

export default function ReviewPage() {
  const [token, setToken] = useState("");
  const [pack, setPack] = useState<{
    items: ReviewItem[];
    dimensions: string[];
    dimension_labels?: Record<string, string>;
    blinded?: boolean;
    blinding_note?: string;
    summary: Record<string, unknown>;
    ai_advisory: Record<string, unknown>;
  } | null>(null);
  const [reviewer, setReviewer] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [filters, setFilters] = useState({ product: "", font: "", status: "", golden: false });
  const [deep, setDeep] = useState<string | null>(null);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [note, setNote] = useState("");

  useEffect(() => {
    const saved = api.getAdminToken();
    if (saved) setToken(saved);
  }, []);

  const load = useCallback(async (t: string) => {
    setError(null);
    try {
      // Blinded: the pack is requested without a reviewer identity, so the
      // backend withholds what other people already decided.
      setPack(await api.getReviewPack(t));
      api.setAdminToken(t);
    } catch (e) {
      setPack(null);
      setError(e instanceof Error ? e.message : "Request failed");
    }
  }, []);

  const decide = useCallback(
    async (item: ReviewItem, decision: Decision, mode: "quick" | "deep") => {
      if (!reviewer.trim()) {
        setError("Enter your name first — every review is attributable.");
        return;
      }
      setBusy(item.item_id);
      setError(null);
      try {
        await api.submitReviewDecision(token, {
          item_id: item.item_id,
          recipe_hash: item.recipe_hash,
          product: item.product,
          font_id: item.technical.font_id,
          feature_set: item.technical.feature_set,
          font_axes: item.technical.font_axes,
          source_text: item.source_text,
          reviewer,
          decision,
          mode,
          scores: mode === "deep" ? scores : null,
          note: note || null,
          engineering: item.engineering,
        });
        setDeep(null);
        setScores({});
        setNote("");
        await load(token);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Request failed");
      } finally {
        setBusy(null);
      }
    },
    [reviewer, token, scores, note, load]
  );

  const items = useMemo(() => {
    if (!pack) return [];
    return pack.items.filter(
      (i) =>
        (!filters.product || i.product === filters.product) &&
        (!filters.font || i.technical.font_id === filters.font) &&
        (!filters.status || i.curation.state === filters.status) &&
        (!filters.golden || i.golden_production_pattern.length > 0)
    );
  }, [pack, filters]);

  const products = useMemo(
    () => Array.from(new Set(pack?.items.map((i) => i.product) ?? [])),
    [pack]
  );
  const fonts = useMemo(
    () => Array.from(new Set(pack?.items.map((i) => i.technical.font_id) ?? [])),
    [pack]
  );

  return (
    <main dir="ltr" className="p-6 max-w-6xl mx-auto text-left">
      <h1 className="text-2xl font-bold mb-1">Art Director Review</h1>
      <p className="text-sm text-gray-600 mb-4">
        Internal. Judge the piece, not the typeface. Engineering gates are already enforced —
        an approval here can never ship something that fails Arabic identity, manufacturing or
        licensing.
      </p>

      <div className="flex flex-wrap gap-2 mb-4">
        <input type="password" data-testid="admin-token" value={token}
          onChange={(e) => setToken(e.target.value)} placeholder="X-Admin-Token"
          className="border rounded px-3 py-2 flex-1 min-w-48" />
        <input data-testid="reviewer-name" value={reviewer}
          onChange={(e) => setReviewer(e.target.value)} placeholder="Your name"
          className="border rounded px-3 py-2 w-48" />
        <button data-testid="load-pack" onClick={() => load(token)}
          className="border rounded px-4 py-2 bg-black text-white">Load pack</button>
      </div>

      {error && <p className="text-red-700 mb-4">{error}</p>}

      {pack && (
        <>
          <div className="text-sm bg-gray-50 border rounded p-3 mb-4">
            <strong>{String(pack.summary.review_items)}</strong> items ·{" "}
            <strong>{String(pack.summary.human_reviews_recorded)}</strong> human reviews recorded ·
            status <strong>{String(pack.summary.human_review_status)}</strong> ·{" "}
            {String(pack.summary.awaiting_human_review)} awaiting review ·{" "}
            AI advisory: {String((pack.ai_advisory as { status: string }).status)}
            {pack.blinded && (
              <p className="mt-1 text-gray-600">{pack.blinding_note}</p>
            )}
          </div>

          <div className="flex flex-wrap gap-2 mb-6 text-sm">
            <select className="border rounded px-2 py-1" value={filters.product}
              onChange={(e) => setFilters({ ...filters, product: e.target.value })}>
              <option value="">All products</option>
              {products.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select className="border rounded px-2 py-1" value={filters.font}
              onChange={(e) => setFilters({ ...filters, font: e.target.value })}>
              <option value="">All fonts</option>
              {fonts.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
            <select className="border rounded px-2 py-1" value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
              <option value="">All statuses</option>
              {["PRODUCTION_RECOMMENDED", "PRODUCTION_ALLOWED", "EXPERIMENTAL", "HIDDEN"].map(
                (s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={filters.golden}
                onChange={(e) => setFilters({ ...filters, golden: e.target.checked })} />
              Proven production pattern only
            </label>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {items.map((item) => (
              <article key={item.item_id} data-testid="review-item"
                className="border rounded overflow-hidden">
                <Proof item={item} />
                <div className="p-4">
                  <div className="flex items-baseline justify-between gap-2">
                    <h2 className="font-semibold">
                      {item.product} · {item.customer_style ?? "—"}
                    </h2>
                    <span className="text-sm text-gray-600">{item.font_family}</span>
                  </div>
                  <p className="text-sm mt-1">
                    <span dir="rtl">{item.source_text}</span> · {item.width_mm}×{item.height_mm} mm
                  </p>

                  <p className="text-sm mt-2">
                    {item.manufacturing_pass ? (
                      <span className="text-green-700">MANUFACTURING PASS</span>
                    ) : (
                      <span className="text-red-700">
                        MANUFACTURING FAIL — approval cannot ship this
                      </span>
                    )}
                    {item.golden_production_pattern.length > 0 && (
                      <span data-testid="golden-badge"
                        className="ml-2 px-2 py-0.5 rounded bg-amber-100 text-amber-900 text-xs">
                        proven production pattern
                      </span>
                    )}
                  </p>

                  <p className="text-xs text-gray-500 mt-1">
                    {item.curation.human_review_status} · {item.curation.state}
                    {item.curation.failed_gates.length > 0 &&
                      ` · blocked: ${item.curation.failed_gates.join(", ")}`}
                  </p>

                  <details className="mt-2">
                    <summary className="text-xs text-gray-500 cursor-pointer">
                      Technical detail
                    </summary>
                    <pre className="text-[10px] bg-gray-50 p-2 rounded mt-1 overflow-x-auto">
{JSON.stringify({ ...item.technical, composition: item.composition,
  engineering: item.engineering }, null, 1)}
                    </pre>
                  </details>

                  <div className="flex flex-wrap gap-2 mt-3">
                    {DECISIONS.map((d) => (
                      <button key={d} data-testid={`decide-${d}`}
                        disabled={busy === item.item_id}
                        onClick={() => decide(item, d, deep === item.item_id ? "deep" : "quick")}
                        className="border rounded px-3 py-1 text-sm hover:bg-gray-50 disabled:opacity-50">
                        {d}
                      </button>
                    ))}
                    <button onClick={() => setDeep(deep === item.item_id ? null : item.item_id)}
                      className="text-sm underline">
                      {deep === item.item_id ? "cancel deep review" : "deep review"}
                    </button>
                  </div>

                  {deep === item.item_id && (
                    <div className="mt-3 border-t pt-3">
                      <p className="text-xs text-gray-600 mb-2">
                        All twelve dimensions, 1–5. Required for a deep review.
                      </p>
                      <div className="grid grid-cols-2 gap-1 text-xs">
                        {pack.dimensions.map((dim) => (
                          <label key={dim} className="flex items-center justify-between gap-2">
                            {pack.dimension_labels?.[dim] ?? dim}
                            <input type="number" min={1} max={5}
                              value={scores[dim] ?? ""}
                              onChange={(e) =>
                                setScores({ ...scores, [dim]: Number(e.target.value) })}
                              className="border rounded w-14 px-1" />
                          </label>
                        ))}
                      </div>
                      <textarea value={note} onChange={(e) => setNote(e.target.value)}
                        placeholder="Reviewer note (optional)"
                        className="border rounded w-full mt-2 px-2 py-1 text-sm" />
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
