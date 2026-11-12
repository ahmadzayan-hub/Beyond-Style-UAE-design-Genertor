"use client";

import { useEffect, useMemo, useState } from "react";
import * as api from "@/lib/api";
import { STRINGS } from "@/lib/i18n";
import { Alert, AppHeader, Button, Chip, EmptyState, Field, Input, Select, Skeleton } from "@/components/ui";

type Card = {
  id: string; name_en: string; name_ar: string; category: string; tags: string[]; status: string;
  action_en: string; action_ar: string; fonts: { font_id: string; family: string; license: string; source_url: string }[];
  influenced_fonts: { font_id: string; family: string }[]; license: string[]; jewelry_suitability: string[];
  manufacturing_score: number | null; manufacturing_safe: boolean;
};
const FAV_KEY = "bs.style.favorites";
const RECENT_KEY = "bs.style.recent";
const MATERIALS = ["silver-925", "gold-18k-yellow", "gold-18k-rose", "gold-18k-white", "platinum"] as const;
const PRODUCTS = ["pendant", "ring", "earrings", "bracelet", "brooch", "keychain", "cufflinks"];
const MOODS = ["classic", "modern", "luxury", "geometric", "minimal", "statement", "manufacturing_safe"];
const AR: Record<string, string> = {
  pendant: "دلاية", ring: "خاتم", earrings: "أقراط", bracelet: "سوار", brooch: "بروش", keychain: "ميدالية", cufflinks: "أزرار أكمام",
  classic: "كلاسيكي", modern: "عصري", luxury: "فخم", geometric: "هندسي", minimal: "بسيط", statement: "لافت", manufacturing_safe: "آمن للتصنيع",
  classical: "كلاسيكي", decorative: "زخرفي", historical: "تاريخي", experimental: "تجريبي", necklace: "قلادة",
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
  // Catalogue load state is explicit: a failed fetch is never shown as an
  // empty catalogue (dashboards/ui-ux-promax rule: never fake "0").
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState("");
  const [previewBusy, setPreviewBusy] = useState<Record<string, boolean>>({});
  const [previewErr, setPreviewErr] = useState<Record<string, boolean>>({});

  function loadCatalogue() {
    setLoadState("loading");
    api.stylesCatalogue()
      .then((r) => { setCards(r.styles || []); setLoadState("ready"); })
      .catch((e: unknown) => { setCards([]); setLoadError(e instanceof Error ? e.message : String(e)); setLoadState("error"); });
  }

  useEffect(() => {
    loadCatalogue();
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
    if (!font || !previewText.trim()) return;
    setPreviewBusy((b) => ({ ...b, [c.id]: true }));
    setPreviewErr((e) => ({ ...e, [c.id]: false }));
    try {
      const svg = await api.fontPreview(font, previewText, material);
      setPreviews((p) => ({ ...p, [c.id]: svg }));
    } catch {
      setPreviewErr((e) => ({ ...e, [c.id]: true }));
    } finally {
      setPreviewBusy((b) => ({ ...b, [c.id]: false }));
    }
  }

  // A preview is rendered for one text + material. When either changes the
  // old SVGs no longer match the inputs, so they are cleared, not kept.
  useEffect(() => { setPreviews({}); setPreviewErr({}); }, [previewText, material]);

  const filtersActive = Boolean(product || mood || q);
  function clearFilters() { setProduct(null); setMood(null); setQ(""); }

  const L = (k: string) => (lang === "ar" ? AR[k] || k : k.replace(/_/g, " "));
  const t = STRINGS[lang];
  const ar = lang === "ar";
  const name = (id: string) => cards.find((c) => c.id === id)?.[ar ? "name_ar" : "name_en"];
  return (
    <main className="mx-auto w-full max-w-5xl px-4 pb-24">
      <AppHeader
        lang={lang}
        onToggleLang={() => setLang(ar ? "en" : "ar")}
        meLabel={t.me_link}
        stylesLabel={t.nav_styles}
        active="styles"
      />
      <h1 className="font-display text-3xl font-bold text-ink-900">{ar ? "متصفح أنماط الخط" : "Style Browser"}</h1>
      <p className="mt-1 max-w-2xl text-sm text-ink-600">
        {ar ? "كل نمط يعرض مصدره ورخصته وتوافره الحقيقي. الأنماط غير المتاحة تحتاج مصدرًا مرخّصًا — لا نقلّد خطًا مقفلاً."
            : "Every style shows its source, license and real availability. Locked styles need a licensed source — we never imitate a locked font."}
      </p>

      <section className="mt-5 rounded-2xl border border-ink-100 bg-white p-4 shadow-soft" aria-label={ar ? "البحث والمعاينة" : "Search and preview"}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label={ar ? "بحث" : "Search"} htmlFor="style-search">
            <Input id="style-search" type="search" value={q} onChange={(e) => setQ(e.target.value)}
                   placeholder={ar ? "اسم النمط أو الخط" : "Style or font name"} data-testid="style-search" />
          </Field>
          <Field label={ar ? "نص المعاينة" : "Preview text"} htmlFor="style-preview-text"
                 hint={ar ? "يُعرض كما كتبته تمامًا" : "Shown exactly as typed"}>
            <Input id="style-preview-text" value={previewText} onChange={(e) => setPreviewText(e.target.value)} dir="auto"
                   className="font-display text-base" data-testid="style-preview-text" />
          </Field>
          <Field label={t.material_label} htmlFor="style-material">
            <Select id="style-material" value={material} onChange={(e) => setMaterial(e.target.value)} data-testid="style-material">
              {MATERIALS.map((m) => <option key={m} value={m}>{t.materials[m]}</option>)}
            </Select>
          </Field>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2" role="group" aria-label={ar ? "المنتج" : "Product"}>
          {PRODUCTS.map((p) => (
            <Chip key={p} selected={product === p} onClick={() => setProduct(product === p ? null : p)} data-testid={`filter-${p}`} className="h-9 px-3">
              {L(p)}
            </Chip>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2" role="group" aria-label={ar ? "الطابع" : "Mood"}>
          {MOODS.map((m) => (
            <Chip key={m} selected={mood === m} onClick={() => setMood(mood === m ? null : m)} data-testid={`filter-${m}`} className="h-9 px-3">
              {L(m)}
            </Chip>
          ))}
        </div>
        {(favs.length > 0 || recent.length > 0) && (
          <p className="mt-3 text-xs text-ink-500" data-testid="style-shortcuts">
            {ar ? "المفضلة" : "Favorites"}: {favs.map(name).filter(Boolean).join("، ") || "—"} ·{" "}
            {ar ? "الأخيرة" : "Recent"}: {recent.map(name).filter(Boolean).join("، ") || "—"}
          </p>
        )}
        {recommended.length > 0 && (
          <p className="mt-1 text-xs text-ink-500">{ar ? "مُوصى به" : "Recommended"}: {recommended.map((c) => (ar ? c.name_ar : c.name_en)).join("، ")}</p>
        )}
      </section>

      {loadState === "ready" && (
        <p className="mt-4 text-xs text-ink-500" aria-live="polite" data-testid="style-count">
          {ar ? `يظهر ${visible.length} من ${cards.length} نمطًا` : `Showing ${visible.length} of ${cards.length} styles`}
          {filtersActive && (
            <button type="button" onClick={clearFilters} className="ms-2 font-medium text-gold-700 underline" data-testid="style-clear-filters">
              {ar ? "مسح الفلاتر" : "Clear filters"}
            </button>
          )}
        </p>
      )}

      {loadState === "loading" && (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="style-loading">
          {[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-56 rounded-2xl" label={ar ? "جارٍ تحميل الأنماط" : "Loading styles"} />)}
        </div>
      )}

      {loadState === "error" && (
        <Alert tone="danger" className="mt-4" data-testid="style-error"
               title={ar ? "تعذّر تحميل كتالوج الأنماط" : "Could not load the style catalogue"}
               action={<Button size="sm" variant="secondary" onClick={loadCatalogue} data-testid="style-retry">{ar ? "إعادة المحاولة" : "Retry"}</Button>}>
          <span dir="ltr" className="font-mono text-xs">GET /api/fonts/styles · {loadError}</span>
        </Alert>
      )}

      {loadState === "ready" && cards.length === 0 && (
        <EmptyState className="mt-4" title={ar ? "لا توجد أنماط في السجل" : "The style registry is empty"}
                    body={ar ? "لم يُرجع الخادم أي نمط. ارفع مصدرًا مرخّصًا من لوحة الخطوط." : "The backend returned no styles. Upload a licensed source from the fonts panel."} />
      )}

      {loadState === "ready" && cards.length > 0 && visible.length === 0 && (
        <div data-testid="style-empty"><EmptyState className="mt-4" title={ar ? "لا يوجد نمط يطابق الفلاتر" : "No style matches these filters"}
                    action={<Button size="sm" variant="secondary" onClick={clearFilters}>{ar ? "مسح الفلاتر" : "Clear filters"}</Button>} /></div>
      )}

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="style-grid">
        {visible.map((c) => {
          const locked = c.status === "UPLOAD_REQUIRED" || c.status === "PARAMETRIC_NOT_BUILT";
          const fav = favs.includes(c.id);
          return (
            <div key={c.id} data-testid={`style-card-${c.id}`}
                 className={`flex flex-col rounded-2xl border bg-white p-4 ${locked ? "border-dashed border-ink-200" : "border-ink-100 shadow-soft"}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-display text-lg font-bold leading-tight text-ink-900">{ar ? c.name_ar : c.name_en}</p>
                  <p className="mt-0.5 text-[11px] text-ink-500">{L(c.category)} · {c.jewelry_suitability.map(L).join("، ")}</p>
                </div>
                <button type="button" onClick={() => toggleFav(c.id)} data-testid={`fav-${c.id}`} aria-pressed={fav}
                        aria-label={ar ? `إضافة ${c.name_ar} إلى المفضلة` : `Favorite ${c.name_en}`}
                        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-lg hover:bg-cream-200 ${fav ? "text-gold-600" : "text-ink-400"}`}>
                  {fav ? "★" : "☆"}
                </button>
              </div>
              <div className="proof-svg surface-paper my-3 flex min-h-[96px] items-center justify-center rounded-xl">
                {previews[c.id] ? <div dangerouslySetInnerHTML={{ __html: previews[c.id] }} /> :
                  locked ? <span className="text-xs text-ink-400">{ar ? "لا معاينة — لا يوجد مصدر" : "No preview — no source"}</span> :
                  <div className="flex flex-col items-center gap-1">
                    <Button size="sm" variant="ghost" onClick={() => loadPreview(c)} loading={!!previewBusy[c.id]}
                            disabled={!previewText.trim()} data-testid={`preview-${c.id}`}>
                      {ar ? "معاينة" : "Preview"}
                    </Button>
                    {previewErr[c.id] && <span className="text-[11px] text-danger-600" role="alert">{ar ? "تعذّرت المعاينة — حاول مرة أخرى" : "Preview failed — try again"}</span>}
                    {!previewText.trim() && <span className="text-[11px] text-ink-400">{ar ? "اكتب نص المعاينة أولًا" : "Type preview text first"}</span>}
                  </div>}
              </div>
              <p className="text-[11px]">
                <span className={`rounded-full px-2 py-0.5 font-semibold ${c.status === "AVAILABLE" ? "bg-ok-50 text-ok-800" : locked ? "bg-cream-200 text-ink-600" : "bg-warn-50 text-warn-800"}`} data-testid={`status-${c.id}`}>
                  {ar ? c.action_ar : c.action_en}
                </span>
              </p>
              <p className="mt-2 text-[11px] leading-relaxed text-ink-500">
                {c.fonts.length > 0 ? `${c.fonts.length} ${ar ? "خط" : "font(s)"}: ${c.fonts.map((f) => f.family).join(", ")}` :
                  c.influenced_fonts.length > 0 ? `${ar ? "مستوحى عبر" : "inspired via"} ${c.influenced_fonts.map((f) => f.family).join(", ")}` : ""}
                {c.license.length > 0 && ` · ${c.license.join(", ")}`}
                {c.manufacturing_score != null && ` · ${ar ? "درجة التصنيع" : "mfg score"} ${Math.round(c.manufacturing_score * 100)}%`}
              </p>
              {locked && <a href="/admin/fonts" className="mt-auto pt-2 text-[11px] font-medium text-gold-700 underline">{ar ? "رفع مصدر مرخّص" : "Upload licensed source"}</a>}
            </div>
          );
        })}
      </div>
    </main>
  );
}
