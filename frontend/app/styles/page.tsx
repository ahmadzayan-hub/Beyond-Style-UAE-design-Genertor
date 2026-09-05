"use client";

import { useEffect, useMemo, useState } from "react";
import * as api from "@/lib/api";

type Card = {
  id: string; name_en: string; name_ar: string; category: string; tags: string[]; status: string;
  action_en: string; action_ar: string; fonts: { font_id: string; family: string; license: string; source_url: string }[];
  influenced_fonts: { font_id: string; family: string }[]; license: string[]; jewelry_suitability: string[];
  manufacturing_score: number | null; manufacturing_safe: boolean;
};
const FAV_KEY = "bs.style.favorites";
const RECENT_KEY = "bs.style.recent";
const PRODUCTS = ["pendant", "ring", "earrings", "bracelet", "brooch", "keychain", "cufflinks"];
const MOODS = ["classic", "modern", "luxury", "geometric", "minimal", "statement", "manufacturing_safe"];
const AR: Record<string, string> = {
  pendant: "دلاية", ring: "خاتم", earrings: "أقراط", bracelet: "سوار", brooch: "بروش", keychain: "ميدالية", cufflinks: "أزرار أكمام",
  classic: "كلاسيكي", modern: "عصري", luxury: "فخم", geometric: "هندسي", minimal: "بسيط", statement: "لافت", manufacturing_safe: "آمن للتصنيع",
  AVAILABLE: "متاح", INFLUENCED_ONLY: "مستوحى فقط", UPLOAD_REQUIRED: "تثبيت / رفع مصدر مرخّص", PARAMETRIC_NOT_BUILT: "لم يُبنَ بعد", ENGINE: "وضع المحرك",
};

/** Style Browser — every card's availability, license and manufacturing
 * score come from the registry and the sweep; locked styles show the
 * "Install / Upload Licensed Source" action instead of a dead control. */
export default function StylesPage() {
  const [lang, setLang] = useState<"ar" | "en">("ar");
  const [cards, setCards] = useState<Card[]>([]);
  const [q, setQ] = useState("");
  const [product, setProduct] = useState<string | null>(null);
  const [mood, setMood] = useState<string | null>(null);
  const [favs, setFavs] = useState<string[]>([]);
  const [recent, setRecent] = useState<string[]>([]);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [previewText, setPreviewText] = useState("ميثه");
  const [material, setMaterial] = useState("gold-18k-yellow");

  useEffect(() => {
    api.stylesCatalogue().then((r) => setCards(r.styles)).catch(() => setCards([]));
    try {
      setFavs(JSON.parse(localStorage.getItem(FAV_KEY) || "[]"));
      setRecent(JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"));
    } catch {}
  }, []);
  useEffect(() => {
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  const visible = useMemo(() => cards.filter((c) => {
    if (product && !c.tags.includes(product)) return false;
    if (mood && !c.tags.includes(mood)) return false;
    if (q && !(c.name_en + c.name_ar + c.fonts.map((f) => f.family).join(" ")).toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  }), [cards, product, mood, q]);

  const recommended = cards.filter((c) => c.status === "AVAILABLE" && c.manufacturing_safe).slice(0, 4);

  function toggleFav(id: string) {
    const next = favs.includes(id) ? favs.filter((f) => f !== id) : [...favs, id];
    setFavs(next);
    try { localStorage.setItem(FAV_KEY, JSON.stringify(next)); } catch {}
  }
  function touch(id: string) {
    const next = [id, ...recent.filter((r) => r !== id)].slice(0, 8);
    setRecent(next);
    try { localStorage.setItem(RECENT_KEY, JSON.stringify(next)); } catch {}
  }
  async function loadPreview(c: Card) {
    touch(c.id);
    const font = c.fonts[0]?.font_id || c.influenced_fonts[0]?.font_id;
    if (!font) return;
    try {
      const svg = await api.fontPreview(font, previewText, material);
      setPreviews((p) => ({ ...p, [c.id]: svg }));
    } catch {}
  }

  const L = (k: string) => (lang === "ar" ? AR[k] || k : k.replace(/_/g, " "));
  return (
    <main className="mx-auto w-full max-w-5xl px-4 pb-24 pt-6">
      <header className="mb-4 flex items-center justify-between">
        <a href="/" className="font-serif text-xl font-bold text-brand-gold">BEYOND STYLE</a>
        <button onClick={() => setLang(lang === "ar" ? "en" : "ar")} className="rounded-full border border-brand-gold px-3 py-1 text-sm">{lang === "ar" ? "English" : "عربي"}</button>
      </header>
      <h1 className="text-2xl font-bold">{lang === "ar" ? "متصفح أنماط الخط" : "Style Browser"}</h1>
      <p className="mt-1 text-sm text-stone-500">
        {lang === "ar" ? "كل نمط يعرض مصدره ورخصته وتوافره الحقيقي. الأنماط غير المتاحة تحتاج مصدرًا مرخّصًا — لا نقلّد خطًا مقفلاً."
                       : "Every style shows its source, license and real availability. Locked styles need a licensed source — we never imitate a locked font."}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={lang === "ar" ? "بحث" : "Search"} data-testid="style-search"
               className="rounded-lg border border-stone-300 p-2 text-sm" />
        <input value={previewText} onChange={(e) => setPreviewText(e.target.value)} dir="auto" data-testid="style-preview-text"
               className="rounded-lg border border-stone-300 p-2 text-sm" />
        <select value={material} onChange={(e) => setMaterial(e.target.value)} className="rounded-lg border border-stone-300 p-2 text-sm">
          {["silver-925", "gold-18k-yellow", "gold-18k-rose", "gold-18k-white", "platinum"].map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        {PRODUCTS.map((p) => (
          <button key={p} onClick={() => setProduct(product === p ? null : p)} data-testid={`filter-${p}`}
                  className={`rounded-full border px-3 py-1 ${product === p ? "border-brand-gold bg-brand-gold text-white" : "border-stone-300 bg-white"}`}>{L(p)}</button>
        ))}
        <span className="mx-1 text-stone-300">|</span>
        {MOODS.map((m) => (
          <button key={m} onClick={() => setMood(mood === m ? null : m)} data-testid={`filter-${m}`}
                  className={`rounded-full border px-3 py-1 ${mood === m ? "border-brand-dark bg-brand-dark text-white" : "border-stone-300 bg-white"}`}>{L(m)}</button>
        ))}
      </div>
      {(favs.length > 0 || recent.length > 0) && (
        <p className="mt-3 text-xs text-stone-500" data-testid="style-shortcuts">
          {lang === "ar" ? "المفضلة" : "Favorites"}: {favs.map((f) => cards.find((c) => c.id === f)?.[lang === "ar" ? "name_ar" : "name_en"]).filter(Boolean).join("، ") || "—"} ·{" "}
          {lang === "ar" ? "الأخيرة" : "Recent"}: {recent.map((f) => cards.find((c) => c.id === f)?.[lang === "ar" ? "name_ar" : "name_en"]).filter(Boolean).join("، ") || "—"}
        </p>
      )}
      {recommended.length > 0 && (
        <p className="mt-1 text-xs text-stone-500">{lang === "ar" ? "مُوصى به" : "Recommended"}: {recommended.map((c) => (lang === "ar" ? c.name_ar : c.name_en)).join("، ")}</p>
      )}
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="style-grid">
        {visible.map((c) => {
          const locked = c.status === "UPLOAD_REQUIRED" || c.status === "PARAMETRIC_NOT_BUILT";
          return (
            <div key={c.id} data-testid={`style-card-${c.id}`} className={`rounded-xl border bg-white p-3 ${locked ? "border-dashed border-stone-300" : "border-stone-200"}`}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold">{lang === "ar" ? c.name_ar : c.name_en}</p>
                  <p className="text-[11px] text-stone-500">{L(c.category)} · {c.jewelry_suitability.map(L).join("، ")}</p>
                </div>
                <button onClick={() => toggleFav(c.id)} data-testid={`fav-${c.id}`} className="text-lg" aria-label="favorite">{favs.includes(c.id) ? "★" : "☆"}</button>
              </div>
              <div className="proof-svg my-2 flex min-h-[90px] items-center justify-center rounded bg-stone-50">
                {previews[c.id] ? <div dangerouslySetInnerHTML={{ __html: previews[c.id] }} /> :
                  (!locked ? <button onClick={() => loadPreview(c)} data-testid={`preview-${c.id}`} className="text-xs text-brand-gold underline">{lang === "ar" ? "معاينة" : "Preview"}</button>
                           : <span className="text-xs text-stone-400">{lang === "ar" ? "لا معاينة — لا يوجد مصدر" : "No preview — no source"}</span>)}
              </div>
              <p className="text-[11px]">
                <span className={`rounded-full px-2 py-0.5 font-semibold ${c.status === "AVAILABLE" ? "bg-emerald-50 text-emerald-800" : locked ? "bg-stone-100 text-stone-600" : "bg-amber-50 text-amber-800"}`} data-testid={`status-${c.id}`}>
                  {lang === "ar" ? c.action_ar : c.action_en}
                </span>
              </p>
              <p className="mt-1 text-[11px] text-stone-500">
                {c.fonts.length > 0 ? `${c.fonts.length} ${lang === "ar" ? "خط" : "font(s)"}: ${c.fonts.map((f) => f.family).join(", ")}` :
                  c.influenced_fonts.length > 0 ? `${lang === "ar" ? "مستوحى عبر" : "inspired via"} ${c.influenced_fonts.map((f) => f.family).join(", ")}` : ""}
                {c.license.length > 0 && ` · ${c.license.join(", ")}`}
                {c.manufacturing_score != null && ` · ${lang === "ar" ? "درجة التصنيع" : "mfg score"} ${Math.round(c.manufacturing_score * 100)}%`}
              </p>
              {locked && <a href="/admin/fonts" className="mt-2 inline-block text-[11px] text-brand-gold underline">{lang === "ar" ? "رفع مصدر مرخّص" : "Upload licensed source"}</a>}
            </div>
          );
        })}
      </div>
    </main>
  );
}
