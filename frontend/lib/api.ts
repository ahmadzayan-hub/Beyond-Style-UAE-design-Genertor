// Thin API client. All domain logic lives in the backend — the frontend
// only orchestrates calls and renders state. The anonymous session token is
// kept in sessionStorage and sent on every request-scoped call.
//
// Production topology: Browser -> Vercel (static/SSR Next.js) -> HTTPS ->
// the FastAPI backend directly (CORS, not a Vercel-side proxy). The
// backend origin comes from NEXT_PUBLIC_API_URL; when unset (local dev)
// calls stay relative and are proxied by next.config.mjs's rewrite to
// BACKEND_URL (default http://localhost:8000) — that rewrite is a local
// dev convenience only and is NOT how production is wired.

const TOKEN_KEY = "bs_session_token";
const DESIGN_KEY = "bs_design_id";
const REQUEST_ID_HEADER = "X-Request-ID";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export type ApiErrorCode =
  | "CONNECTION_FAILED"
  | "REFERENCE_NOT_READY"
  | "GENERATION_FAILED"
  | "NO_VALID_CANDIDATES"
  | "ARABIC_VALIDATION_FAILED"
  | "BACKEND_UNAVAILABLE"
  | "SESSION_EXPIRED"
  | "RATE_LIMITED"
  | "UNKNOWN";

export class ApiError extends Error {
  code: ApiErrorCode;
  status?: number;
  requestId?: string;
  constructor(message: string, code: ApiErrorCode, status?: number, requestId?: string) {
    super(message);
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { "X-Session-Token": t } : {};
}

/** Never throws a raw fetch/TypeError — always a typed ApiError so the
 * UI can distinguish "never reached the backend" from a real backend
 * error response. */
async function doFetch(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(apiUrl(path), init);
  } catch {
    throw new ApiError(
      "Could not reach the backend.",
      "CONNECTION_FAILED"
    );
  }
}

async function jsonOrThrow(res: Response) {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    let code: ApiErrorCode = "UNKNOWN";
    let requestId: string | undefined = res.headers.get(REQUEST_ID_HEADER) || undefined;
    // Our backend ALWAYS answers errors with structured JSON carrying
    // error_code. A non-JSON error body therefore means the response came
    // from something that is NOT our backend (Vercel's proxy, a CDN, a
    // misconfigured NEXT_PUBLIC_API_URL) — and must never be dressed up as
    // an application state like "session expired".
    let fromBackend = false;
    try {
      const body = await res.json();
      fromBackend = true;
      if (typeof body.detail === "string") detail = body.detail;
      if (typeof body.error_code === "string") code = body.error_code as ApiErrorCode;
      if (typeof body.request_id === "string") requestId = body.request_id;
    } catch {
      // Non-JSON error body — an intermediary answered, not the backend.
    }
    if (code === "UNKNOWN") {
      if (!fromBackend) {
        // The request never reached a working backend. Seen in production
        // when NEXT_PUBLIC_API_URL is unset and /api/* falls into the
        // dev-only rewrite (Vercel: DNS_HOSTNAME_RESOLVED_PRIVATE → 404).
        code = "BACKEND_UNAVAILABLE";
      } else if (res.status === 503) code = "BACKEND_UNAVAILABLE";
      else if (res.status === 429) code = "RATE_LIMITED";
      else if (res.status === 404) code = "SESSION_EXPIRED";
      else code = "GENERATION_FAILED";
    }
    throw new ApiError(detail, code, res.status, requestId);
  }
  return res.json();
}

export async function createDesign(text: string, productType = "pendant") {
  const body = await jsonOrThrow(
    await doFetch("/api/designs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, product_type: productType }),
    })
  );
  try {
    sessionStorage.setItem(TOKEN_KEY, body.session_token);
    sessionStorage.setItem(DESIGN_KEY, body.design_id);
  } catch {}
  return body;
}

export async function uploadReference(designId: string, file: File, message: string | null) {
  const form = new FormData();
  form.append("file", file);
  form.append("provenance", "UNKNOWN");
  if (message) form.append("customer_message", message);
  return jsonOrThrow(
    await doFetch(`/api/designs/${designId}/references`, {
      method: "POST",
      headers: authHeaders(),
      body: form,
    })
  );
}

export async function analyzeReference(designId: string, referenceId: string) {
  return jsonOrThrow(
    await doFetch(`/api/designs/${designId}/references/${referenceId}/analyze`, {
      method: "POST",
      headers: authHeaders(),
    })
  );
}

export async function updateBrief(designId: string, brief: object) {
  return jsonOrThrow(
    await doFetch(`/api/designs/${designId}/brief`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(brief),
    })
  );
}

export async function confirmText(designId: string, confirmedText: string) {
  return jsonOrThrow(
    await doFetch(`/api/designs/${designId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ confirmed_text: confirmedText }),
    })
  );
}

export async function generateCandidates(designId: string) {
  return jsonOrThrow(
    await doFetch(`/api/designs/${designId}/candidates`, {
      method: "POST",
      headers: authHeaders(),
    })
  );
}

/** Optional `material` returns the deterministic metal render of the same
 * geometry (gradients + lighting in SVG — never AI, never a different path). */
export async function candidateSvg(designId: string, candidateId: string, material?: string): Promise<string> {
  const q = material ? `?material=${encodeURIComponent(material)}` : "";
  const res = await doFetch(`/api/designs/${designId}/candidates/${candidateId}/svg${q}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, "GENERATION_FAILED", res.status);
  return res.text();
}

export async function selectCandidate(designId: string, candidateId: string) {
  return jsonOrThrow(
    await doFetch(`/api/designs/${designId}/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ candidate_id: candidateId }),
    })
  );
}

export async function versionSvg(versionId: string, material?: string, scene?: string): Promise<string> {
  const q = material
    ? `?material=${encodeURIComponent(material)}${scene ? `&scene=${encodeURIComponent(scene)}` : ""}`
    : "";
  const res = await doFetch(`/api/versions/${versionId}/svg${q}`, { headers: authHeaders() });
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, "GENERATION_FAILED", res.status);
  return res.text();
}

export async function mesh3dPayload(versionId: string) {
  // Canonical 2D polygons + real thickness/dimensions/weight for the
  // client-side Three.js extrusion. Visualization only.
  return jsonOrThrow(
    await doFetch(`/api/versions/${versionId}/mesh3d`, { headers: authHeaders() })
  );
}

export async function agreementProofSvg(versionId: string): Promise<string> {
  // Dimensioned approval artifact: the design with its real mm dimensions
  // and spec block drawn on — what the customer actually agrees to.
  const res = await doFetch(`/api/versions/${versionId}/agreement-proof`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, "GENERATION_FAILED", res.status);
  return res.text();
}

export async function editVersion(versionId: string, overrides: object, note: string | null) {
  return jsonOrThrow(
    await doFetch(`/api/versions/${versionId}/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ recipe_overrides: overrides, note, created_by: "customer-copilot" }),
    })
  );
}

export async function repairOptions(versionId: string) {
  return jsonOrThrow(
    await doFetch(`/api/versions/${versionId}/repair-options`, { headers: authHeaders() })
  );
}

export async function applyRepair(versionId: string) {
  return jsonOrThrow(
    await doFetch(`/api/versions/${versionId}/repair`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({}),
    })
  );
}

export async function generatePreview(versionId: string, opts: object) {
  return jsonOrThrow(
    await doFetch(`/api/visual/versions/${versionId}/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(opts),
    })
  );
}

export async function previewImageUrl(generationId: string): Promise<string> {
  const res = await doFetch(`/api/visual/generations/${generationId}/image`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, "GENERATION_FAILED", res.status);
  return URL.createObjectURL(await res.blob());
}

export async function getVersion(versionId: string) {
  return jsonOrThrow(await doFetch(`/api/versions/${versionId}`, { headers: authHeaders() }));
}

export async function approveVersion(
  versionId: string,
  confirmedText: string,
  sourceSha: string,
  geometryHash: string
) {
  return jsonOrThrow(
    await doFetch(`/api/versions/${versionId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        confirmed_text: confirmedText,
        source_text_sha256: sourceSha,
        geometry_hash: geometryHash,
        approved_by: "customer-web",
        approval_method: "web_checkbox",
      }),
    })
  );
}

export type ExportFormat = "svg" | "dxf" | "pdf" | "png";

/** Workshop export. Resolves to the Export Fidelity Gate verdict the
 * backend computed by re-importing the file it just wrote. */
export async function downloadExport(versionId: string, fmt: ExportFormat): Promise<string> {
  const res = await doFetch(`/api/versions/${versionId}/export/${fmt}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, "GENERATION_FAILED", res.status);
  const fidelity = res.headers.get("X-Export-Fidelity") || "UNKNOWN";
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `beyond-style-${versionId.slice(0, 8)}.${fmt}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return fidelity;
}

// --- Admin (Golden Production Cases) ---
// Staff-only. The admin token is never bundled into the build: it is
// entered by the operator and kept in sessionStorage for that tab only.

const ADMIN_TOKEN_KEY = "bs_admin_token";

export function getAdminToken(): string | null {
  try {
    return sessionStorage.getItem(ADMIN_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAdminToken(token: string): void {
  try {
    sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
  } catch {
    /* storage unavailable — the caller keeps the token in component state */
  }
}

function adminHeaders(token: string): Record<string, string> {
  return { "X-Admin-Token": token };
}

export async function listGoldenCases(token: string) {
  return jsonOrThrow(await doFetch("/api/admin/golden-cases", { headers: adminHeaders(token) }));
}

export async function getGoldenCase(token: string, caseId: string) {
  return jsonOrThrow(
    await doFetch(`/api/admin/golden-cases/${encodeURIComponent(caseId)}`, {
      headers: adminHeaders(token),
    })
  );
}

// --- Art Director review (internal, admin-token gated) ---

export async function getReviewPack(token: string, maxPerProduct = 3) {
  return jsonOrThrow(
    await doFetch(`/api/admin/review/pack?max_per_product=${maxPerProduct}`, {
      headers: adminHeaders(token),
    })
  );
}

export async function submitReviewDecision(token: string, body: Record<string, unknown>) {
  return jsonOrThrow(
    await doFetch("/api/admin/review/decision", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...adminHeaders(token) },
      body: JSON.stringify(body),
    })
  );
}

export async function getReviewHistory(token: string, itemId: string) {
  return jsonOrThrow(
    await doFetch(`/api/admin/review/history/${encodeURIComponent(itemId)}`, {
      headers: adminHeaders(token),
    })
  );
}

// ---- Public customer validation (anonymous, no staff token) ----
export async function validationPack() {
  return jsonOrThrow(await doFetch("/api/validation/pack", {}));
}

export async function submitVote(body: object) {
  return jsonOrThrow(
    await doFetch("/api/validation/response", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}


// ---- Text Integrity Engine ----
export async function inspectText(text: string) {
  return jsonOrThrow(
    await doFetch(`/api/designs/integrity/inspect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, product_type: "pendant" }),
    })
  );
}

export async function versionIntegrity(versionId: string) {
  return jsonOrThrow(await doFetch(`/api/versions/${versionId}/integrity`, { headers: authHeaders() }));
}

// ---- Arabic Calligraphy Source Registry ----
export async function stylesCatalogue() {
  return jsonOrThrow(await doFetch(`/api/fonts/styles`));
}

export async function fontRegistry() {
  return jsonOrThrow(await doFetch(`/api/fonts/registry`));
}

export async function fontPreview(fontId: string, text: string, material?: string): Promise<string> {
  const q = new URLSearchParams({ text });
  if (material) q.set("material", material);
  const res = await doFetch(`/api/fonts/preview/${encodeURIComponent(fontId)}?${q}`);
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, "GENERATION_FAILED", res.status);
  return res.text();
}

// ---- Jewelry Manufacturing Gate ----
export async function jewelryQa(versionId: string, material?: string, thicknessMm?: number, targetG?: number) {
  const q = new URLSearchParams();
  if (material) q.set("material", material);
  if (thicknessMm) q.set("thickness_mm", String(thicknessMm));
  if (targetG) q.set("target_weight_g", String(targetG));
  return jsonOrThrow(await doFetch(`/api/versions/${versionId}/jewelry-qa?${q}`, { headers: authHeaders() }));
}

export async function readiness(versionId: string) {
  return jsonOrThrow(await doFetch(`/api/versions/${versionId}/readiness`, { headers: authHeaders() }));
}

export async function listExports(versionId: string) {
  return jsonOrThrow(await doFetch(`/api/versions/${versionId}/exports`, { headers: authHeaders() }));
}

// ---------------------------------------------------------------- Pro mode
// Vector edit operations: versioned, text-protected, fail-safe (a rejected
// op returns 422 with the reason and creates no version).

export interface VectorOp {
  op: string;
  params: Record<string, unknown>;
}

export async function vectorOps(versionId: string) {
  return jsonOrThrow(await doFetch(`/api/versions/${versionId}/vector-ops`, { headers: authHeaders() }));
}

export async function vectorEditPreview(versionId: string, ops: VectorOp[]) {
  return jsonOrThrow(
    await doFetch(`/api/versions/${versionId}/vector-edit/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ ops }),
    })
  );
}

export async function vectorEdit(versionId: string, ops: VectorOp[], note: string | null) {
  return jsonOrThrow(
    await doFetch(`/api/versions/${versionId}/vector-edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ ops, note, created_by: "designer-pro" }),
    })
  );
}

export async function applyRepairById(versionId: string, repairId: string) {
  return jsonOrThrow(
    await doFetch(`/api/versions/${versionId}/repair`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ repair_id: repairId }),
    })
  );
}

// ------------------------------------------------- secure approval link
// Single-use, expiring link bound to one exact version. Minting needs the
// owner session; viewing/approving needs only the token (no session).

export async function createApprovalLink(versionId: string, ttlHours = 72) {
  return jsonOrThrow(
    await doFetch(`/api/versions/${versionId}/approval-link`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ ttl_hours: ttlHours, created_by: "studio" }),
    })
  );
}

export async function approvalLinkView(token: string) {
  return jsonOrThrow(await doFetch(`/api/approval-links/${encodeURIComponent(token)}`));
}

export async function approveViaLink(token: string, confirmedText: string, approverName: string) {
  return jsonOrThrow(
    await doFetch(`/api/approval-links/${encodeURIComponent(token)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmed_text: confirmedText, approver_name: approverName, accept_statement: true }),
    })
  );
}
