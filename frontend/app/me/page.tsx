"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import * as api from "@/lib/api";
import { Lang, STRINGS } from "@/lib/i18n";

interface MyDesign {
  design_id: string; text: string; product_type: string; state: string; confirmed: boolean;
  created_at: string; versions: number; latest_version_status: string | null; approved: boolean;
}

/** Customer identity: passwordless login (contact + one-time code), then
 *  the customer's own designs — resumable on this device. Honest about
 *  code delivery: without a provider the code is not sent (dev echo only). */
export default function MyDesignsPage() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("ar");
  const t = STRINGS[lang];
  const [contact, setContact] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [started, setStarted] = useState<any>(null);
  const [me, setMe] = useState<any>(null);
  const [designs, setDesigns] = useState<MyDesign[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.documentElement.dir = t.dir;
    document.documentElement.lang = lang;
  }, [lang, t.dir]);

  async function load() {
    try {
      const m = await api.me();
      setMe(m);
      setDesigns((await api.myDesigns()).designs);
    } catch {
      setMe(null);
      setDesigns(null);
    }
  }
  useEffect(() => { if (api.getCustomerToken()) load(); }, []);

  async function start() {
    setBusy(true); setError(null);
    try { setStarted(await api.loginStart(contact)); } catch (e: any) { setError(e?.message ?? String(e)); } finally { setBusy(false); }
  }
  async function verify() {
    setBusy(true); setError(null);
    try { await api.loginVerify(contact, code, name); setStarted(null); setCode(""); await load(); }
    catch (e: any) { setError(e?.message ?? String(e)); } finally { setBusy(false); }
  }
  async function resume(d: MyDesign) {
    setBusy(true); setError(null);
    try { await api.resumeDesign(d.design_id); router.push(`/?design=${d.design_id}`); }
    catch (e: any) { setError(e?.message ?? String(e)); setBusy(false); }
  }

  const input = "mt-1 w-full rounded border border-stone-300 p-3";
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-lg flex-col gap-4 px-4 pb-16 pt-6">
      <header className="flex items-center justify-between">
        <a href="/" className="font-serif text-xl font-bold tracking-tight text-brand-gold">BEYOND STYLE</a>
        <button onClick={() => setLang(lang === "ar" ? "en" : "ar")} className="rounded-full border border-brand-gold px-3 py-1 text-sm" data-testid="lang-toggle">
          {lang === "ar" ? "English" : "عربي"}
        </button>
      </header>
      <h2 className="text-xl font-bold">{t.me_title}</h2>
      {error && <div role="alert" data-testid="me-error" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>}

      {!me && (
        <section className="flex flex-col gap-3 rounded-xl border border-stone-200 bg-white p-4" data-testid="login-box">
          <p className="text-sm text-stone-600">{t.me_intro}</p>
          {!started ? (
            <>
              <label className="text-sm">{t.me_contact}
                <input dir="ltr" value={contact} onChange={(e) => setContact(e.target.value)} data-testid="login-contact" className={input} />
              </label>
              <button data-testid="login-start" disabled={busy || contact.trim().length < 3} onClick={start}
                      className="rounded-xl bg-brand-dark p-3 text-sm font-semibold text-white disabled:opacity-40">{t.me_send_code}</button>
            </>
          ) : (
            <>
              <p className="text-sm" data-testid="login-delivery">
                {started.delivery?.status === "SKIPPED_EXTERNAL_PROVIDER" ? t.me_code_skipped : `${t.me_code_sent} ${started.contact_masked}`}
              </p>
              {started.dev_code && <p className="rounded bg-amber-50 p-2 text-xs" data-testid="login-dev-code">{t.me_dev_code}: <code dir="ltr">{started.dev_code}</code></p>}
              <label className="text-sm">{t.me_code}
                <input dir="ltr" inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} data-testid="login-code" className={input} />
              </label>
              <label className="text-sm">{t.me_name}
                <input value={name} onChange={(e) => setName(e.target.value)} data-testid="login-name" className={input} />
              </label>
              <button data-testid="login-verify" disabled={busy || code.trim().length < 4} onClick={verify}
                      className="rounded-xl bg-brand-dark p-3 text-sm font-semibold text-white disabled:opacity-40">{t.me_verify}</button>
            </>
          )}
        </section>
      )}

      {me && (
        <section className="flex flex-col gap-3" data-testid="me-box">
          <div className="flex items-center justify-between rounded-lg bg-white p-3 text-sm">
            <span data-testid="me-identity">{t.me_signed_in_as} <b>{me.display_name || me.contact_masked}</b></span>
            <button data-testid="me-logout" onClick={async () => { await api.logoutCustomer(); setMe(null); setDesigns(null); }} className="text-stone-500 underline">{t.me_logout}</button>
          </div>
          {designs && designs.length === 0 && <p className="text-sm text-stone-500" data-testid="me-empty">{t.me_empty}</p>}
          {designs && designs.map((d) => (
            <div key={d.design_id} className="flex items-center justify-between rounded-xl border border-stone-200 bg-white p-4" data-testid={`my-design-${d.design_id}`}>
              <div>
                <p dir="auto" className="text-lg font-bold">{d.text}</p>
                <p className="text-xs text-stone-500">
                  {d.product_type} · {d.state} · {d.versions} {t.me_versions}{d.approved ? ` · ${t.me_approved} ✓` : ""}
                </p>
              </div>
              <button data-testid={`resume-${d.design_id}`} disabled={busy} onClick={() => resume(d)}
                      className="rounded-lg bg-brand-dark px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{t.me_resume}</button>
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
