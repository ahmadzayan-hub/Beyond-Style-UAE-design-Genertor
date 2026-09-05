"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import * as api from "@/lib/api";
import { Lang, STRINGS } from "@/lib/i18n";

interface View {
  state: string;
  version_number: number;
  immutable_source_text: string;
  geometry_hash: string;
  expires_at: string;
  statement_ar: string;
  statement_en: string;
  agreement_proof_svg: string;
}

/** Public customer approval page (no session): exact text + dimensioned
 *  proof of ONE version, retype-to-confirm, single-use approval. */
export default function ApproveByLinkPage() {
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";
  const [lang, setLang] = useState<Lang>("ar");
  const t = STRINGS[lang];
  const [view, setView] = useState<View | null>(null);
  const [invalid, setInvalid] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ approval_hash: string } | null>(null);

  useEffect(() => {
    document.documentElement.dir = t.dir;
    document.documentElement.lang = lang;
  }, [lang, t.dir]);

  useEffect(() => {
    if (!token) return;
    api.approvalLinkView(token).then(setView).catch((e: any) => setInvalid(e?.message ?? String(e)));
  }, [token]);

  const matches = view ? typed.normalize("NFC") === view.immutable_source_text : false;

  async function approve() {
    if (!view || !matches) return;
    setBusy(true); setError(null);
    try {
      setDone(await api.approveViaLink(token, typed.normalize("NFC"), name));
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally { setBusy(false); }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-lg flex-col gap-4 px-4 pb-16 pt-6">
      <header className="flex items-center justify-between">
        <h1 className="font-serif text-xl font-bold tracking-tight text-brand-gold">BEYOND STYLE</h1>
        <button onClick={() => setLang(lang === "ar" ? "en" : "ar")} className="rounded-full border border-brand-gold px-3 py-1 text-sm" data-testid="lang-toggle">
          {lang === "ar" ? "English" : "عربي"}
        </button>
      </header>
      <h2 className="text-xl font-bold">{t.link_page_title}</h2>
      {invalid && (
        <div role="alert" data-testid="link-invalid" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          {t.link_invalid} {invalid}
        </div>
      )}
      {view && !done && (
        <>
          <p className="text-sm text-stone-600">{t.link_page_intro}</p>
          <p className="text-xs text-stone-500">{t.link_version} {view.version_number} · {t.link_expires}: {new Date(view.expires_at).toLocaleString()}</p>
          <div className="proof-svg-large rounded-xl border border-stone-200 bg-white p-4" data-testid="link-proof"
               dangerouslySetInnerHTML={{ __html: view.agreement_proof_svg }} />
          <div data-testid="link-text-display" dir="auto"
               className="rounded-xl border-2 border-brand-gold bg-white p-5 text-center text-3xl font-bold whitespace-pre-line">
            {view.immutable_source_text}
          </div>
          <label className="text-sm">
            {t.link_retype}
            <input dir="auto" value={typed} onChange={(e) => setTyped(e.target.value)} data-testid="link-retype"
                   className="mt-1 w-full rounded border border-stone-300 p-3 text-xl" />
            {typed && !matches && <span className="text-xs text-red-700" data-testid="link-mismatch">{t.link_mismatch}</span>}
          </label>
          <label className="text-sm">
            {t.link_name}
            <input value={name} onChange={(e) => setName(e.target.value)} data-testid="link-name"
                   className="mt-1 w-full rounded border border-stone-300 p-3" />
          </label>
          <p className="rounded-lg bg-white p-4 text-sm font-medium">
            {lang === "ar" ? view.statement_ar : view.statement_en}
            <br />
            <span className="text-xs text-stone-400">{lang === "ar" ? view.statement_en : view.statement_ar}</span>
          </p>
          {error && <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800" data-testid="link-error">{error}</div>}
          <button data-testid="link-approve" disabled={!matches || busy} onClick={approve}
                  className="rounded-xl bg-brand-dark p-4 text-lg font-semibold text-white disabled:opacity-40">
            {t.link_approve}
          </button>
        </>
      )}
      {done && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4" data-testid="link-approved">
          <p className="text-lg font-bold text-emerald-800">{t.link_done}</p>
          <p className="mt-2 break-all text-xs text-stone-500" data-testid="link-approval-hash">{done.approval_hash}</p>
        </div>
      )}
    </main>
  );
}
