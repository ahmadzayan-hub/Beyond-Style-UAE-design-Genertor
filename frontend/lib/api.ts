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
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      if (typeof body.error_code === "string") code = body.error_code as ApiErrorCode;
      if (typeof body.request_id === "string") requestId = body.request_id;
    } catch {
      // Non-JSON error body (e.g. an intermediary/proxy 502/504) — status
      // code alone still tells us enough to classify it below.
    }
    if (code === "UNKNOWN") {
      if (res.status === 503) code = "BACKEND_UNAVAILABLE";
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

export async function candidateSvg(designId: string, candidateId: string): Promise<string> {
  const res = await doFetch(`/api/designs/${designId}/candidates/${candidateId}/svg`, {
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

export async function versionSvg(versionId: string): Promise<string> {
  const res = await doFetch(`/api/versions/${versionId}/svg`, { headers: authHeaders() });
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

export async function downloadExport(versionId: string, fmt: "svg" | "dxf") {
  const res = await doFetch(`/api/versions/${versionId}/export/${fmt}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, "GENERATION_FAILED", res.status);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `beyond-style-${versionId.slice(0, 8)}.${fmt}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
