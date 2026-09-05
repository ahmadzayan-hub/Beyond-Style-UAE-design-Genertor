"use client";

import { useState } from "react";

/** Admin: licensed font upload. Server inspects and shapes the binary and
 * records the license as evidence; nothing is imitated or faked. */
export default function AdminFontsPage() {
  const [token, setToken] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState({
    font_id: "", family: "", license_name: "", license_text: "", source_url: "", rights: "COMMERCIAL_LICENSED",
    script_family: "thuluth", capability: "THULUTH", style_influence: "", tags: "", owner: "", web_use: false, redistribution: false,
  });
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const base = process.env.NEXT_PUBLIC_API_URL || "";

  async function submit(dryRun: boolean) {
    if (!file) return;
    setError(null); setResult(null);
    const fd = new FormData();
    fd.append("file", file);
    Object.entries(form).forEach(([k, v]) => fd.append(k, String(v)));
    fd.append("dry_run", String(dryRun));
    const res = await fetch(`${base}/api/admin/fonts`, { method: "POST", body: fd, headers: { "X-Admin-Token": token } });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) setError(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail));
    else setResult(body);
  }
  const set = (k: string, v: any) => setForm((f) => ({ ...f, [k]: v }));
  return (
    <main className="mx-auto w-full max-w-2xl px-4 pb-24 pt-6" dir="ltr">
      <a href="/" className="font-serif text-xl font-bold text-brand-gold">BEYOND STYLE</a>
      <h1 className="mt-3 text-2xl font-bold">Licensed font upload</h1>
      <p className="mt-1 text-sm text-stone-500">TTF / OTF / WOFF / WOFF2. The binary is stored privately (never served), inspected (Arabic coverage, contextual forms, marks, embedding bits), shaped on the golden names and activated by its declared rights. Keep the EULA text as evidence.</p>
      <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="X-Admin-Token" type="password" className="mt-4 w-full rounded border border-stone-300 p-2 text-sm" />
      <input type="file" accept=".ttf,.otf,.woff,.woff2" onChange={(e) => setFile(e.target.files?.[0] || null)} className="mt-3 text-sm" data-testid="font-file" />
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 text-sm">
        {[["font_id", "font id (lowercase-hyphen)"], ["family", "family name"], ["license_name", "license / EULA name"], ["source_url", "source URL"], ["owner", "owner / buyer"], ["tags", "tags (comma)"], ["style_influence", "style influence (optional)"]].map(([k, ph]) => (
          <input key={k} value={(form as any)[k]} onChange={(e) => set(k, e.target.value)} placeholder={ph} className="rounded border border-stone-300 p-2" />
        ))}
        <select value={form.rights} onChange={(e) => set("rights", e.target.value)} className="rounded border border-stone-300 p-2">
          {["COMMERCIAL_LICENSED", "VERIFIED_OPEN_SOURCE", "CUSTOMER_OWNED", "INTERNAL_ONLY", "UNKNOWN_RIGHTS"].map((r) => <option key={r}>{r}</option>)}
        </select>
        <select value={form.script_family} onChange={(e) => set("script_family", e.target.value)} className="rounded border border-stone-300 p-2">
          {["thuluth", "diwani", "naskh", "ruqaa", "kufi", "nastaliq", "modern_arabic"].map((r) => <option key={r}>{r}</option>)}
        </select>
        <select value={form.capability} onChange={(e) => set("capability", e.target.value)} className="rounded border border-stone-300 p-2">
          {["THULUTH", "DIWANI", "NASKH", "RUQAA", "KUFI", "MODERN_KUFI", "GEOMETRIC_KUFI", "NASTALIQ", "MODERN_ARABIC", "DISPLAY", "BOLD", "LOGO", "NASTALIQ_LEVANTINE", "FATIMID_FOLIATED", "HISTORICAL", "CALLIGRAFFITI"].map((r) => <option key={r}>{r}</option>)}
        </select>
        <label className="flex items-center gap-2"><input type="checkbox" checked={form.web_use} onChange={(e) => set("web_use", e.target.checked)} /> web use permitted</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={form.redistribution} onChange={(e) => set("redistribution", e.target.checked)} /> redistribution permitted</label>
      </div>
      <textarea value={form.license_text} onChange={(e) => set("license_text", e.target.value)} placeholder="Paste the EULA / license text (required evidence)" rows={5} className="mt-2 w-full rounded border border-stone-300 p-2 text-sm" />
      <div className="mt-3 flex gap-3">
        <button onClick={() => submit(true)} disabled={!file || !token} className="rounded-xl border border-brand-gold p-3 text-sm font-semibold text-brand-gold disabled:opacity-40">Inspect (dry run)</button>
        <button onClick={() => submit(false)} disabled={!file || !token} className="rounded-xl bg-brand-dark p-3 text-sm font-semibold text-white disabled:opacity-40">Register &amp; activate</button>
      </div>
      {error && <pre className="mt-3 whitespace-pre-wrap rounded bg-red-50 p-3 text-xs text-red-800">{error}</pre>}
      {result && <pre className="mt-3 max-h-96 overflow-auto rounded bg-stone-50 p-3 text-[11px]">{JSON.stringify(result, null, 2)}</pre>}
    </main>
  );
}
