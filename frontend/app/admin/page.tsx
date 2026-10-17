"use client";

// Staff dashboard. Every figure on this page is read from a backend
// endpoint at render time — nothing is computed client-side from guesses
// and nothing is cached across sessions. Sections that the backend cannot
// answer (no admin token, a 503, an endpoint that is slow) say so in
// place instead of showing an empty chart that looks like "zero".

import { useCallback, useEffect, useMemo, useState } from "react";
import * as api from "@/lib/api";
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Skeleton } from "@/components/ui";

type Readiness = { status: string; components: Record<string, { status: string; [k: string]: unknown }> };
type Health = { status: string; schema_version: string; build_sha: string };
type GoldenCase = {
  case_id: string; product_type: string; language: string; layout_style: string | null;
  memory_tier: string; evidence_tier: string; production_result: string; customer_sentiment: string;
  customer_approved: boolean; design_fidelity_score: number | null; source_text_status: string;
};
type Order = { order_id: string; state: string; material: string; rework_count: number; created_at: string };
type AiStatus = {
  ai_mode: string; allow_paid_providers: boolean;
  providers: Record<string, { model_id: string; status: string; license?: string }>;
  claude: { sdk_installed: boolean; credentials_configured: boolean; routing: string };
  gpt_image_2: { enabled_flag: boolean; sdk_installed: boolean; key_configured: boolean; role: string };
  deterministic_fallback: { status: string; note: string };
};

const ORDER_STATES = ["NEW", "DESIGN_REVIEW", "TECHNICAL_CHECK", "APPROVED", "MANUFACTURING", "QC", "REWORK", "READY", "DELIVERED"];

function count<T>(rows: T[], key: (r: T) => string): [string, number][] {
  const m = new Map<string, number>();
  for (const r of rows) m.set(key(r), (m.get(key(r)) ?? 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1]);
}

/** Horizontal bar list. Plain divs, no chart library: the numbers are
 *  small (tens of rows) and the bars must stay legible at 360 px. */
function Bars({ rows, total, testId }: { rows: [string, number][]; total: number; testId: string }) {
  if (rows.length === 0) return <p className="text-xs text-ink-500">—</p>;
  return (
    <ul className="flex flex-col gap-1.5" data-testid={testId}>
      {rows.map(([label, n]) => (
        <li key={label} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 text-xs">
          <div className="min-w-0">
            <div className="flex justify-between gap-2">
              <span className="truncate text-ink-800">{label}</span>
              <span className="tabular-nums text-ink-500">{n}</span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-cream-200">
              <div className="h-full rounded-full bg-gold-500" style={{ width: `${total ? Math.round((n / total) * 100) : 0}%` }} />
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function Stat({ label, value, tone, testId }: { label: string; value: string | number; tone?: "ok" | "warn" | "danger" | "neutral"; testId?: string }) {
  const color = tone === "ok" ? "text-ok-800" : tone === "warn" ? "text-warn-800" : tone === "danger" ? "text-danger-800" : "text-ink-900";
  return (
    <Card padding="sm" className="min-w-0">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">{label}</p>
      <p className={`mt-1 truncate font-display text-2xl ${color}`} data-testid={testId}>{value}</p>
    </Card>
  );
}

export default function AdminDashboard() {
  const [token, setToken] = useState("");
  const [health, setHealth] = useState<Health | null | "error">(null);
  const [ready, setReady] = useState<Readiness | null | "error">(null);
  const [ai, setAi] = useState<AiStatus | null | "error">(null);
  const [cases, setCases] = useState<GoldenCase[] | null>(null);
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [wave, setWave] = useState<any | null>(null);
  const [waveBusy, setWaveBusy] = useState(false);
  const [waveError, setWaveError] = useState<string | null>(null);
  const [loadedAt, setLoadedAt] = useState<string | null>(null);

  // Public probes need no token.
  const loadPublic = useCallback(async () => {
    const [h, r, a] = await Promise.allSettled([api.health(), api.serviceReadiness(), api.aiStatus()]);
    setHealth(h.status === "fulfilled" ? h.value : "error");
    setReady(r.status === "fulfilled" ? r.value : "error");
    setAi(a.status === "fulfilled" ? a.value : "error");
    setLoadedAt(new Date().toLocaleTimeString());
  }, []);

  const loadAdmin = useCallback(async (t: string) => {
    setAdminError(null);
    const [c, o] = await Promise.allSettled([api.listGoldenCases(t), api.workshopOrders(t)]);
    if (c.status === "fulfilled") { setCases(c.value.cases); api.setAdminToken(t); } else { setCases(null); }
    if (o.status === "fulfilled") setOrders(o.value.orders); else setOrders(null);
    const failed = [c, o].find((x) => x.status === "rejected") as PromiseRejectedResult | undefined;
    if (failed) setAdminError(failed.reason instanceof Error ? failed.reason.message : "Request failed");
  }, []);

  useEffect(() => {
    loadPublic();
    const saved = api.getAdminToken();
    if (saved) { setToken(saved); loadAdmin(saved); }
  }, [loadPublic, loadAdmin]);

  const loadWave = useCallback(async () => {
    setWaveBusy(true); setWaveError(null);
    try { setWave(await api.reviewWave1(token)); }
    catch (e) { setWaveError(e instanceof Error ? e.message : "Request failed"); }
    finally { setWaveBusy(false); }
  }, [token]);

  const caseStats = useMemo(() => {
    if (!cases) return null;
    return {
      total: cases.length,
      approved: cases.filter((c) => c.customer_approved).length,
      byProduct: count(cases, (c) => c.product_type),
      byTier: count(cases, (c) => c.memory_tier),
      byResult: count(cases, (c) => c.production_result),
      byTextStatus: count(cases, (c) => c.source_text_status),
      fidelity: cases.filter((c) => c.design_fidelity_score != null).map((c) => c.design_fidelity_score as number),
    };
  }, [cases]);

  const orderStats = useMemo(() => {
    if (!orders) return null;
    const byState = new Map<string, number>();
    for (const o of orders) byState.set(o.state, (byState.get(o.state) ?? 0) + 1);
    return {
      total: orders.length,
      open: orders.filter((o) => o.state !== "DELIVERED").length,
      rework: orders.filter((o) => o.rework_count > 0).length,
      pipeline: ORDER_STATES.map((s) => [s, byState.get(s) ?? 0] as [string, number]),
    };
  }, [orders]);

  const readyComponents = ready && ready !== "error" ? Object.entries(ready.components) : [];
  const readyDown = readyComponents.filter(([, v]) => v.status !== "ok");

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-4 pb-16 pt-6" dir="ltr">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-gold-600">Beyond Style · Staff</p>
          <h1 className="font-display text-3xl text-ink-900">Production dashboard</h1>
          <p className="mt-1 text-sm text-ink-500">
            Live reads from the backend{loadedAt ? ` · refreshed ${loadedAt}` : ""}. No figure on this page is cached or estimated.
          </p>
        </div>
        <nav className="flex flex-wrap gap-2 text-sm">
          <a className="rounded-full border border-ink-200 bg-white px-3 py-1.5 hover:border-gold-300" href="/admin/review">Art Director review</a>
          <a className="rounded-full border border-ink-200 bg-white px-3 py-1.5 hover:border-gold-300" href="/admin/golden-cases">Golden cases</a>
          <a className="rounded-full border border-ink-200 bg-white px-3 py-1.5 hover:border-gold-300" href="/admin/fonts">Fonts</a>
          <Button variant="secondary" size="sm" onClick={() => { loadPublic(); if (token) loadAdmin(token); }}>Refresh</Button>
        </nav>
      </header>

      {/* ---- Service health (public) ---- */}
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-testid="dash-health">
        <Stat label="Backend" value={health === "error" ? "unreachable" : health ? health.status : "…"} tone={health === "error" ? "danger" : health ? "ok" : "neutral"} testId="dash-backend" />
        <Stat label="Build" value={health && health !== "error" ? health.build_sha.slice(0, 12) : "—"} />
        <Stat
          label="Readiness"
          value={ready === "error" ? "unreachable" : ready ? ready.status : "…"}
          tone={ready === "error" ? "danger" : ready ? (ready.status === "ready" ? "ok" : "danger") : "neutral"}
          testId="dash-ready"
        />
        <Stat label="Components down" value={ready && ready !== "error" ? readyDown.length : "—"} tone={readyDown.length ? "danger" : "ok"} />
      </section>
      {ready && ready !== "error" && (
        <Card title="Readiness components" subtitle="From GET /ready — the same probe the production monitor uses.">
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="dash-components">
            {readyComponents.map(([name, v]) => (
              <li key={name} className="flex items-center justify-between gap-2 rounded-xl bg-cream-50 px-3 py-2 text-sm">
                <span className="truncate text-ink-800">{name.replace(/_/g, " ")}</span>
                <Badge tone={v.status === "ok" ? "ok" : "danger"}>{v.status}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* ---- AI providers (public, honest) ---- */}
      <Card title="AI providers" subtitle="Per-model availability. The Arabic, geometry and manufacturing engines never depend on any of these.">
        {ai === "error" ? (
          <Alert tone="danger">Could not read /api/ai/status.</Alert>
        ) : !ai ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2 text-xs">
              <Badge tone="neutral">mode: {ai.ai_mode}</Badge>
              <Badge tone={ai.allow_paid_providers ? "warn" : "neutral"}>paid providers: {ai.allow_paid_providers ? "allowed" : "off"}</Badge>
              <Badge tone={ai.claude.credentials_configured ? "ok" : "neutral"}>Claude: {ai.claude.credentials_configured ? "configured" : "no credentials"}</Badge>
              <Badge tone={ai.gpt_image_2.key_configured ? "ok" : "neutral"}>GPT-Image-2: {ai.gpt_image_2.key_configured ? "configured" : "no key"} · {ai.gpt_image_2.role}</Badge>
              <Badge tone="ok">{ai.deterministic_fallback.status.replace(/_/g, " ")}</Badge>
            </div>
            <ul className="grid gap-2 sm:grid-cols-2" data-testid="dash-ai-providers">
              {Object.entries(ai.providers).map(([role, p]) => (
                <li key={role} className="rounded-xl bg-cream-50 px-3 py-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-ink-800">{role.replace(/_/g, " ")}</span>
                    <Badge tone={p.status === "ok" || p.status === "available" ? "ok" : "warn"}>{p.status}</Badge>
                  </div>
                  <p className="mt-0.5 text-ink-500">{p.model_id}{p.license ? ` · ${p.license}` : ""}</p>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {/* ---- Staff token gate ---- */}
      <Card title="Staff data" subtitle="Golden production memory, workshop orders and review slates need the admin token (kept in this tab only).">
        <form
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
          onSubmit={(e) => { e.preventDefault(); loadAdmin(token); }}
        >
          <Field label="X-Admin-Token" className="flex-1" htmlFor="admin-token">
            <Input id="admin-token" type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" data-testid="dash-token" />
          </Field>
          <Button type="submit" disabled={!token} data-testid="dash-load">Load</Button>
        </form>
        {adminError && <Alert tone="danger" className="mt-3">{adminError}</Alert>}
      </Card>

      {/* ---- Golden production memory ---- */}
      <section className="grid gap-4 lg:grid-cols-2">
        <Card title="Golden production memory" subtitle="Owner-supplied real cases the generator ranks against. Source: /api/admin/golden-cases." data-testid="dash-golden">
          {!cases ? (
            <EmptyState title="Not loaded" body="Enter the admin token to read the golden cases." />
          ) : cases.length === 0 ? (
            <EmptyState title="No golden cases in this database" body="The seed runs against the production database; this environment has none." />
          ) : caseStats && (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-3 gap-2">
                <Stat label="Cases" value={caseStats.total} testId="dash-golden-total" />
                <Stat label="Customer approved" value={caseStats.approved} tone="ok" />
                <Stat
                  label="Fidelity (mean)"
                  value={caseStats.fidelity.length ? (caseStats.fidelity.reduce((a, b) => a + b, 0) / caseStats.fidelity.length).toFixed(2) : "n/a"}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div><p className="mb-1.5 text-xs font-semibold text-ink-700">By product</p><Bars rows={caseStats.byProduct} total={caseStats.total} testId="dash-golden-product" /></div>
                <div><p className="mb-1.5 text-xs font-semibold text-ink-700">Memory tier</p><Bars rows={caseStats.byTier} total={caseStats.total} testId="dash-golden-tier" /></div>
                <div><p className="mb-1.5 text-xs font-semibold text-ink-700">Production result</p><Bars rows={caseStats.byResult} total={caseStats.total} testId="dash-golden-result" /></div>
                <div><p className="mb-1.5 text-xs font-semibold text-ink-700">Source-text status</p><Bars rows={caseStats.byTextStatus} total={caseStats.total} testId="dash-golden-text" /></div>
              </div>
              <p className="text-[11px] text-ink-500">
                Source text that is still UNCONFIRMED was never read off a photo by software; it waits for the owner to type it on the case page.
              </p>
            </div>
          )}
        </Card>

        {/* ---- Workshop ---- */}
        <Card title="Workshop orders" subtitle="State machine with no skipped states. Source: /api/workshop/orders." data-testid="dash-workshop">
          {!orders ? (
            <EmptyState title="Not loaded" body="Enter the admin token to read workshop orders." />
          ) : orderStats && (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-3 gap-2">
                <Stat label="Orders" value={orderStats.total} testId="dash-orders-total" />
                <Stat label="Open" value={orderStats.open} tone={orderStats.open ? "warn" : "neutral"} />
                <Stat label="With rework" value={orderStats.rework} tone={orderStats.rework ? "danger" : "neutral"} />
              </div>
              <Bars rows={orderStats.pipeline} total={Math.max(orderStats.total, 1)} testId="dash-orders-pipeline" />
              {orders.length === 0 && (
                <p className="text-[11px] text-ink-500">No orders yet: customer ordering is not built, so orders only appear when staff create one from an approved version.</p>
              )}
            </div>
          )}
        </Card>
      </section>

      {/* ---- Review wave (on demand: the backend renders the slate) ---- */}
      <Card
        title="Human review — wave 1"
        subtitle="Prioritised review slate and per-product comparison readiness. Loaded on demand because the backend renders every proof when asked."
        action={<Button size="sm" variant="secondary" disabled={!token || waveBusy} loading={waveBusy} onClick={loadWave} data-testid="dash-wave-load">Load slate</Button>}
        data-testid="dash-wave"
      >
        {waveError && <Alert tone="danger">{waveError}</Alert>}
        {!wave ? (
          <p className="text-xs text-ink-500">Not loaded.</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              <Badge tone="neutral">items: {Array.isArray(wave.items) ? wave.items.length : 0}</Badge>
              <Badge tone="neutral">dimensions: {Array.isArray(wave.dimensions) ? wave.dimensions.length : 0}</Badge>
              {wave.blinded && <Badge tone="info">blinded</Badge>}
            </div>
            {wave.comparison_readiness && (
              <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(wave.comparison_readiness as Record<string, any>).map(([product, r]) => (
                  <li key={product} className="rounded-xl bg-cream-50 px-3 py-2 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-ink-800">{product}</span>
                      <Badge tone={r.status === "PRODUCT_COMPARISON_READY" ? "ok" : "warn"}>{String(r.status).replace(/_/g, " ")}</Badge>
                    </div>
                    <p className="mt-0.5 text-ink-500">
                      families reviewed {r.families_reviewed}/{r.families_in_corpus} · with enough reviews {r.families_with_enough_reviews}/{r.required_families}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-[11px] text-ink-500">Every family verdict stays INSUFFICIENT_HUMAN_REVIEW_EVIDENCE until enough genuine reviews exist; no engineering or AI score substitutes for one.</p>
          </div>
        )}
      </Card>
    </main>
  );
}
