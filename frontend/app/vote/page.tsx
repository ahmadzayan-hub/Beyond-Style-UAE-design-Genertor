"use client";

// Public customer validation: score real, manufacturable proofs. Anonymous
// (a random token in this browser groups one person's answers); nothing
// technical is shown — a customer reacts to the piece.

import { useEffect, useState } from "react";
import * as api from "@/lib/api";

interface Item {
  item_id: string;
  product: string;
  customer_style: string;
  source_text: string;
  width_mm: number;
  height_mm: number;
  proof_path_d: string;
  proof_view: [number, number];
}

const WOULD_BUY = ["YES", "MAYBE", "NO"] as const;

function token(): string {
  try {
    const k = "bs_vote_token";
    let t = localStorage.getItem(k);
    if (!t) {
      t = Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
      localStorage.setItem(k, t);
    }
    return t;
  } catch {
    return "anon-" + Math.random().toString(16).slice(2);
  }
}

export default function VotePage() {
  const [pack, setPack] = useState<{ pack_id: string; items: Item[] } | null>(null);
  const [done, setDone] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.validationPack().then(setPack).catch(() => setError("تعذر تحميل التصاميم. حاول لاحقاً."));
  }, []);

  async function submit(item: Item, form: FormData) {
    setError(null);
    try {
      await api.submitVote({
        pack_id: pack!.pack_id,
        item_id: item.item_id,
        respondent_token: token(),
        would_buy: String(form.get("would_buy")),
        premium_feel: Number(form.get("premium_feel")),
        readability: Number(form.get("readability")),
        uniqueness: Number(form.get("uniqueness")),
        website: String(form.get("website") || ""),
      });
      setDone((d) => ({ ...d, [item.item_id]: true }));
    } catch {
      setError("تعذر إرسال رأيك. حاول مرة أخرى.");
    }
  }

  return (
    <main dir="rtl" className="mx-auto flex min-h-screen w-full max-w-lg flex-col gap-5 px-4 pb-24 pt-6">
      <h1 className="font-serif text-xl font-bold text-brand-gold">BEYOND STYLE</h1>
      <h2 className="text-2xl font-bold">رأيك يهمنا</h2>
      <p className="text-sm text-stone-500">قيّم كل تصميم كما تراه — لا توجد إجابة صحيحة. إجاباتك مجهولة الهوية.</p>
      {error && <p className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {!pack && !error && <div className="h-40 animate-pulse rounded bg-stone-100" />}
      {pack?.items.map((item) => {
        const [w, h] = item.proof_view;
        return (
          <form
            key={item.item_id}
            data-testid="vote-card"
            className="flex flex-col gap-3 rounded-xl border border-stone-200 bg-white p-4"
            onSubmit={(e) => {
              e.preventDefault();
              submit(item, new FormData(e.currentTarget));
            }}
          >
            <svg viewBox={`0 0 ${w} ${h}`} className="mx-auto max-h-48 w-full" role="img" aria-label={item.source_text}>
              <path d={item.proof_path_d} fill="#111" fillRule="evenodd" />
            </svg>
            <p className="text-center text-lg font-bold">{item.source_text}</p>
            <p className="text-center text-xs text-stone-500">{item.customer_style} · {item.width_mm.toFixed(0)}×{item.height_mm.toFixed(0)} مم</p>
            {done[item.item_id] ? (
              <p className="text-center text-sm text-emerald-700">شكراً — تم تسجيل رأيك ✓</p>
            ) : (
              <>
                <fieldset className="flex justify-center gap-2 text-sm">
                  <legend className="mb-1 w-full text-center text-xs text-stone-500">هل تشتريه؟</legend>
                  {WOULD_BUY.map((v, i) => (
                    <label key={v} className="rounded-full border border-stone-300 px-3 py-1">
                      <input type="radio" name="would_buy" value={v} defaultChecked={i === 1} className="me-1" />
                      {v === "YES" ? "نعم" : v === "MAYBE" ? "ربما" : "لا"}
                    </label>
                  ))}
                </fieldset>
                {(["premium_feel", "readability", "uniqueness"] as const).map((k) => (
                  <label key={k} className="text-xs">
                    {k === "premium_feel" ? "إحساس فاخر" : k === "readability" ? "وضوح القراءة" : "تميّز التصميم"}
                    <input type="range" name={k} min={1} max={5} defaultValue={3} className="w-full accent-brand-gold" />
                  </label>
                ))}
                <input type="text" name="website" tabIndex={-1} autoComplete="off" className="hidden" aria-hidden="true" />
                <button type="submit" className="rounded-lg bg-brand-dark py-2 text-sm font-semibold text-white">أرسل رأيي</button>
              </>
            )}
          </form>
        );
      })}
      {pack && pack.items.length === 0 && <p className="text-sm text-stone-500">لا توجد تصاميم للتقييم حالياً.</p>}
    </main>
  );
}
