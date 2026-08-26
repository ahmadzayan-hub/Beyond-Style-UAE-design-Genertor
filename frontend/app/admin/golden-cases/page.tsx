"use client";

// Staff view over the Golden Production Cases memory tier. Everything
// rendered here comes from the backend — nothing is stubbed. Customer
// conversation screenshots are deliberately absent: they are registered
// by content hash and not stored, so the feedback section shows the
// normalized sentence and says why the original is missing.

import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/api";

interface CaseSummary {
  case_id: string;
  product_type: string;
  language: string;
  layout_style: string | null;
  memory_tier: string;
  evidence_tier: string;
  ranking_weight: string;
  tier_weight: number;
  production_result: string;
  customer_sentiment: string;
  customer_approved: boolean;
  design_fidelity_score: number | null;
  source_text_status: string;
}

interface EvidenceItem {
  role: string;
  sha256: string;
  width: number;
  height: number;
  storage_key: string | null;
  storage_status: string;
  note: string;
}

interface CaseDetail extends CaseSummary {
  sections: {
    concept: EvidenceItem[];
    reference_style: EvidenceItem[];
    layout_proof: EvidenceItem[];
    final_product: EvidenceItem[];
    customer_feedback: {
      normalized_feedback: string | null;
      sentiment: string;
      approved: boolean;
      original_conversation_stored: boolean;
      privacy_note: string;
    };
    production_result: Record<string, unknown>;
    design_dna: Record<string, unknown>;
    lessons_learned: string[];
    stage_comparison: {
      stages: string[];
      measurement_method: string;
      computed_from_vector_geometry: boolean;
      dimensions: Record<string, { score: number | null; note?: string; status?: string }>;
      not_assessed: string[];
      aggregate_score: number | null;
    } | null;
  };
  text_truth: {
    customer_source_text: string | null;
    primary_names: string[] | null;
    status: string;
    authority: string;
    sha256: string | null;
  };
  rights_provenance: string;
  privacy_status: string;
}

function Evidence({ title, items }: { title: string; items: EvidenceItem[] }) {
  return (
    <section className="mb-6">
      <h3 className="font-semibold mb-2">{title}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-gray-500">No evidence recorded for this stage.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item.sha256} className="border rounded p-3 text-sm">
              <div className="font-mono text-xs text-gray-500">
                {item.role} · {item.width}×{item.height} · {item.sha256.slice(0, 16)}…
              </div>
              <div>{item.note}</div>
              <div className="text-xs mt-1">
                {item.storage_key ? (
                  <span className="text-green-700">stored in private object storage</span>
                ) : (
                  <span className="text-amber-700">binary not uploaded ({item.storage_status})</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function GoldenCasesPage() {
  const [token, setToken] = useState("");
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const saved = api.getAdminToken();
    if (saved) setToken(saved);
  }, []);

  const load = useCallback(async (t: string) => {
    setError(null);
    try {
      const data = await api.listGoldenCases(t);
      setCases(data.cases);
      api.setAdminToken(t);
    } catch (e) {
      setCases(null);
      setError(e instanceof Error ? e.message : "Request failed");
    }
  }, []);

  const open = useCallback(
    async (caseId: string) => {
      setError(null);
      try {
        setDetail(await api.getGoldenCase(token, caseId));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Request failed");
      }
    },
    [token]
  );

  return (
    <main dir="ltr" className="p-6 max-w-4xl mx-auto text-left">
      <h1 className="text-2xl font-bold mb-1">Golden Production Cases</h1>
      <p className="text-sm text-gray-600 mb-6">
        Real manufactured, delivered and customer-approved orders. Highest-weight design
        memory: retrieval reuses their DesignDNA and construction logic, never their geometry.
      </p>

      <div className="flex gap-2 mb-6">
        <input
          type="password"
          data-testid="admin-token"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="X-Admin-Token"
          className="border rounded px-3 py-2 flex-1"
        />
        <button
          data-testid="admin-load"
          onClick={() => load(token)}
          className="border rounded px-4 py-2 bg-black text-white"
        >
          Load
        </button>
      </div>

      {error && <p className="text-red-700 mb-4">{error}</p>}

      {cases && (
        <ul className="mb-8 space-y-2">
          {cases.map((c) => (
            <li key={c.case_id}>
              <button
                data-testid="golden-case-row"
                onClick={() => open(c.case_id)}
                className="w-full text-left border rounded p-3 hover:bg-gray-50"
              >
                <div className="font-medium">{c.case_id}</div>
                <div className="text-sm text-gray-600">
                  {c.product_type} · {c.language} · {c.memory_tier} · weight {c.tier_weight} ·
                  fidelity {c.design_fidelity_score ?? "—"}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}

      {detail && (
        <article data-testid="golden-case-detail" className="border-t pt-6">
          <h2 className="text-xl font-bold mb-4">{detail.case_id}</h2>

          <section className="mb-6">
            <h3 className="font-semibold mb-2">Confirmed text</h3>
            <p className="text-sm">
              {detail.text_truth.customer_source_text ? (
                <span className="font-mono">
                  {detail.text_truth.primary_names?.join(" · ") ??
                    detail.text_truth.customer_source_text}
                </span>
              ) : (
                <span className="text-amber-700">
                  Not yet verified — {detail.text_truth.status}. This case contributes style
                  memory only until an order record supplies the exact text.
                </span>
              )}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              authority: {detail.text_truth.authority}
            </p>
          </section>

          <Evidence title="Concept" items={detail.sections.concept} />
          <Evidence title="Reference Style" items={detail.sections.reference_style} />
          <Evidence title="Layout Proof / Workshop Drawing" items={detail.sections.layout_proof} />
          <Evidence title="Final Product" items={detail.sections.final_product} />

          <section className="mb-6">
            <h3 className="font-semibold mb-2">Customer Feedback</h3>
            <p className="text-sm">{detail.sections.customer_feedback.normalized_feedback}</p>
            <p className="text-sm text-gray-600">
              sentiment: {detail.sections.customer_feedback.sentiment} · approved:{" "}
              {String(detail.sections.customer_feedback.approved)}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {detail.sections.customer_feedback.privacy_note}
            </p>
          </section>

          <section className="mb-6">
            <h3 className="font-semibold mb-2">Production Result</h3>
            <pre className="text-xs bg-gray-50 p-3 rounded overflow-x-auto">
              {JSON.stringify(detail.sections.production_result, null, 2)}
            </pre>
          </section>

          {detail.sections.stage_comparison && (
            <section className="mb-6">
              <h3 className="font-semibold mb-2">
                Stage Comparison ({detail.sections.stage_comparison.stages.join(" → ")})
              </h3>
              <p className="text-xs text-gray-500 mb-2">
                {detail.sections.stage_comparison.measurement_method} — not computed from vector
                geometry.
              </p>
              <ul className="text-sm space-y-1">
                {Object.entries(detail.sections.stage_comparison.dimensions).map(([k, v]) => (
                  <li key={k}>
                    <span className="font-mono">{k}</span>:{" "}
                    {v.score === null ? (
                      <span className="text-amber-700">{v.status ?? "NOT_ASSESSED"}</span>
                    ) : (
                      v.score
                    )}
                    {v.note ? <span className="text-gray-500"> — {v.note}</span> : null}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="mb-6">
            <h3 className="font-semibold mb-2">DesignDNA</h3>
            <pre className="text-xs bg-gray-50 p-3 rounded overflow-x-auto">
              {JSON.stringify(detail.sections.design_dna, null, 2)}
            </pre>
          </section>

          <section className="mb-6">
            <h3 className="font-semibold mb-2">Lessons Learned</h3>
            <ul className="list-disc ps-5 text-sm space-y-1">
              {detail.sections.lessons_learned.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </section>

          <p className="text-xs text-gray-500">
            rights: {detail.rights_provenance} · privacy: {detail.privacy_status}
          </p>
        </article>
      )}
    </main>
  );
}
