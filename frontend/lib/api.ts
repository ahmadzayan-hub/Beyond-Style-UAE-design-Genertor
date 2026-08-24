// Thin API client. All domain logic lives in the backend — the frontend
// only orchestrates calls and renders state. The anonymous session token is
// kept in sessionStorage and sent on every request-scoped call.

const TOKEN_KEY = "bs_session_token";
const DESIGN_KEY = "bs_design_id";

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

async function jsonOrThrow(res: Response) {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {}
    const err = new Error(detail) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function createDesign(text: string, productType = "pendant") {
  const body = await jsonOrThrow(
    await fetch("/api/designs", {
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
    await fetch(`/api/designs/${designId}/references`, {
      method: "POST",
      headers: authHeaders(),
      body: form,
    })
  );
}

export async function updateBrief(designId: string, brief: object) {
  return jsonOrThrow(
    await fetch(`/api/designs/${designId}/brief`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(brief),
    })
  );
}

export async function confirmText(designId: string, confirmedText: string) {
  return jsonOrThrow(
    await fetch(`/api/designs/${designId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ confirmed_text: confirmedText }),
    })
  );
}

export async function generateCandidates(designId: string) {
  return jsonOrThrow(
    await fetch(`/api/designs/${designId}/candidates`, {
      method: "POST",
      headers: authHeaders(),
    })
  );
}

export async function candidateSvg(designId: string, candidateId: string): Promise<string> {
  const res = await fetch(`/api/designs/${designId}/candidates/${candidateId}/svg`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.text();
}

export async function selectCandidate(designId: string, candidateId: string) {
  return jsonOrThrow(
    await fetch(`/api/designs/${designId}/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ candidate_id: candidateId }),
    })
  );
}

export async function versionSvg(versionId: string): Promise<string> {
  const res = await fetch(`/api/versions/${versionId}/svg`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.text();
}

export async function repairOptions(versionId: string) {
  return jsonOrThrow(
    await fetch(`/api/versions/${versionId}/repair-options`, { headers: authHeaders() })
  );
}

export async function applyRepair(versionId: string) {
  return jsonOrThrow(
    await fetch(`/api/versions/${versionId}/repair`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({}),
    })
  );
}

export async function getVersion(versionId: string) {
  return jsonOrThrow(await fetch(`/api/versions/${versionId}`, { headers: authHeaders() }));
}

export async function approveVersion(
  versionId: string,
  confirmedText: string,
  sourceSha: string,
  geometryHash: string
) {
  return jsonOrThrow(
    await fetch(`/api/versions/${versionId}/approve`, {
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
  const res = await fetch(`/api/versions/${versionId}/export/${fmt}`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
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
