"use client";

import { useRef } from "react";
import type { Strings } from "./types";
import { Button, Card, Chip, Field, Hero, Input, Range, Select, TextArea } from "@/components/ui";

/** Step 1 of the Golden Path: customer text, optional reference image with
 * style strength + message, product choice (ring fields), style intent.
 * Every data-testid is unchanged from the original screen — the E2E suite
 * drives this step by test id. */
export interface StartStepProps {
  t: Strings;
  text: string; setText: (v: string) => void;
  message: string; setMessage: (v: string) => void;
  refFile: File | null; setRefFile: (f: File | null) => void;
  refPreview: string | null; setRefPreview: (v: string | null) => void;
  styleStrength: number; setStyleStrength: (v: number) => void;
  styleIntent: string | null; setStyleIntent: (v: string | null) => void;
  scriptFamily: string | null; setScriptFamily: (v: string | null) => void;
  /** Style catalogue from the registry (availability computed server-side). */
  styleCards?: { id: string; name_en: string; name_ar: string; status: string; action_en: string; action_ar: string }[];
  lang?: "ar" | "en";
  material: string; setMaterial: (v: string) => void;
  productType: "pendant" | "ring"; setProductType: (v: "pendant" | "ring") => void;
  ringSize: number; setRingSize: (v: number) => void;
  bandHeight: number; setBandHeight: (v: number) => void;
  innerText: string; setInnerText: (v: string) => void;
  busy: boolean; busyLabel: string | null;
  onStart: () => void;
}

const FAMILY_IMAGES: Record<string, string> = {
  necklace: "/brand/family-necklace.jpg",
  bracelet: "/brand/family-bracelet.jpg",
  cufflinks: "/brand/family-cufflinks.jpg",
};

export default function StartStep({
  t, text, setText, message, setMessage, refFile, setRefFile, refPreview, setRefPreview,
  styleStrength, setStyleStrength, styleIntent, setStyleIntent, scriptFamily, setScriptFamily,
  styleCards, lang, material, setMaterial, productType, setProductType,
  ringSize, setRingSize, bandHeight, setBandHeight, innerText, setInnerText,
  busy, busyLabel, onStart,
}: StartStepProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const ar = lang === "ar";
  return (
    <section className="flex flex-col gap-6 animate-fade-up">
      <Hero
        title={t.hero_title}
        subtitle={t.hero_subtitle}
        points={t.hero_points}
        imageLabel={t.hero_image_label}
      />

      <div className="grid gap-6 md:grid-cols-[1fr_300px] md:items-start">
        <div className="flex flex-col gap-5">
          <Card padding="lg">
            <div className="mb-4">
              <h2 className="font-display text-2xl text-ink-900">{t.start_title}</h2>
              <p className="mt-1 text-sm text-ink-500">{t.start_subtitle}</p>
            </div>
            <Field htmlFor="gp-text">
              <Input
                id="gp-text"
                size="lg"
                data-testid="text-input"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={t.text_placeholder}
                autoComplete="off"
                className="font-display"
              />
            </Field>

            <div className="mt-4 rounded-xl border border-dashed border-ink-200 bg-cream-50 p-4">
              <button
                type="button"
                onClick={() => fileInput.current?.click()}
                className="flex w-full items-center gap-3 text-start text-sm font-semibold text-gold-700"
                data-testid="upload-button"
              >
                <span aria-hidden className="flex h-9 w-9 items-center justify-center rounded-full bg-gold-50 text-base">⇡</span>
                <span>
                  {t.upload_reference}
                  <span className="block text-xs font-normal text-ink-500">{t.upload_hint}</span>
                </span>
              </button>
              <input
                ref={fileInput}
                data-testid="file-input"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0] || null;
                  setRefFile(f);
                  setRefPreview(f ? URL.createObjectURL(f) : null);
                }}
              />
              {refPreview && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={refPreview}
                  alt="reference"
                  data-testid="reference-preview"
                  className="mt-3 max-h-40 rounded-lg object-contain"
                />
              )}
              {refFile && (
                <div className="mt-3 flex flex-col gap-3">
                  <Range
                    data-testid="style-strength"
                    label={`${t.strength_original} ↔ ${t.strength_similar}`}
                    valueLabel={`${t.style_strength} ${Math.round(styleStrength * 100)}%`}
                    min={0} max={1} step={0.1} value={styleStrength}
                    onChange={(e) => setStyleStrength(Number(e.target.value))}
                  />
                  <TextArea
                    data-testid="message-input"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder={t.message_placeholder}
                    rows={2}
                  />
                </div>
              )}
            </div>
          </Card>

          <Card title={t.product_label}>
            <div className="flex flex-wrap gap-2">
              {(["pendant", "ring"] as const).map((p) => (
                <Chip key={p} data-testid={`product-${p}`} selected={productType === p} onClick={() => setProductType(p)}>
                  {t.products[p]}
                </Chip>
              ))}
            </div>
            {productType === "ring" && (
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <Field label={t.ring_size_label}>
                  <Select data-testid="ring-size" value={ringSize} onChange={(e) => setRingSize(Number(e.target.value))}>
                    {Array.from({ length: 27 }, (_, i) => 44 + i).map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </Select>
                </Field>
                <Field label={t.inner_engraving_label}>
                  <Input
                    data-testid="inner-text-input"
                    value={innerText}
                    onChange={(e) => setInnerText(e.target.value)}
                    placeholder={t.inner_engraving_hint}
                  />
                </Field>
                <Field label={t.band_height_label}>
                  <Select data-testid="band-height" value={bandHeight} onChange={(e) => setBandHeight(Number(e.target.value))}>
                    {[5.5, 6.5, 7.5, 8.5].map((h) => (
                      <option key={h} value={h}>{h}</option>
                    ))}
                  </Select>
                </Field>
              </div>
            )}
          </Card>

          <Card
            title={t.script_label}
            action={
              <a href="/styles" className="text-xs font-medium text-gold-700 underline-offset-2 hover:underline" data-testid="style-browser-link">
                {t.style_browser_link}
              </a>
            }
          >
            <div className="flex flex-wrap gap-2">
              {styleCards && styleCards.length > 0
                ? styleCards.filter((c) => c.status !== "ENGINE").map((c) => {
                    const locked = c.status === "UPLOAD_REQUIRED" || c.status === "PARAMETRIC_NOT_BUILT";
                    const key = c.id === "kufi_traditional" ? "kufi" : c.id === "nastaliq_persian" ? "nastaliq" : c.id;
                    return (
                      <Chip
                        key={c.id}
                        data-testid={`script-${key}`}
                        disabled={locked}
                        locked={locked}
                        selected={scriptFamily === key}
                        title={ar ? c.action_ar : c.action_en}
                        onClick={() => setScriptFamily(scriptFamily === key ? null : key)}
                        trailing={
                          c.status === "INFLUENCED_ONLY"
                            ? <span className="text-[10px] opacity-70">({t.style_status.INFLUENCED_ONLY})</span>
                            : locked ? <span className="text-[10px]" aria-hidden>🔒</span> : undefined
                        }
                      >
                        {ar ? c.name_ar : c.name_en}
                      </Chip>
                    );
                  })
                : Object.entries(t.scripts).map(([key, label]) => (
                    <Chip key={key} data-testid={`script-${key}`} selected={scriptFamily === key} onClick={() => setScriptFamily(scriptFamily === key ? null : key)}>
                      {label}
                    </Chip>
                  ))}
            </div>
            {(scriptFamily === "thuluth" || scriptFamily === "diwani") && (
              <p className="mt-3 text-xs text-ink-500" data-testid="script-influenced-note">
                {t.script_note_influenced}
              </p>
            )}
          </Card>

          <Card title={t.material_label}>
            <div className="flex flex-wrap gap-2">
              {Object.entries(t.materials).map(([key, label]) => (
                <Chip
                  key={key}
                  data-testid={`material-${key}`}
                  selected={material === key}
                  onClick={() => setMaterial(key)}
                  leading={<span aria-hidden className={`h-3 w-3 rounded-full ring-1 ring-black/10 ${MATERIAL_SWATCH[key] ?? "bg-ink-300"}`} />}
                >
                  {label}
                </Chip>
              ))}
            </div>
          </Card>

          <Card title={t.style_label}>
            <div className="flex flex-wrap gap-2">
              {Object.entries(t.styles).map(([key, label]) => (
                <Chip key={key} data-testid={`style-${key}`} selected={styleIntent === key} onClick={() => setStyleIntent(styleIntent === key ? null : key)}>
                  {label}
                </Chip>
              ))}
            </div>
          </Card>

          {busyLabel && (
            <p className="text-center text-sm text-ink-600" data-testid="busy-label" role="status">
              {busyLabel}
            </p>
          )}
          <Button
            size="lg"
            block
            data-testid="start-continue"
            disabled={!text.trim() || busy}
            loading={busy}
            onClick={onStart}
          >
            {t.continue}
          </Button>
        </div>

        <aside className="hidden md:block">
          <Card padding="sm" title={t.product_families_title} subtitle={t.product_families_note}>
            <ul className="flex flex-col gap-2">
              {(Object.keys(FAMILY_IMAGES) as Array<keyof typeof FAMILY_IMAGES>).map((k) => (
                <li key={k} className="flex items-center gap-3 rounded-xl bg-cream-50 p-2">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={FAMILY_IMAGES[k]} alt="" aria-hidden loading="lazy" decoding="async" className="h-14 w-14 rounded-lg object-cover" />
                  <span className="text-sm font-medium text-ink-800">{t.product_families[k as "necklace" | "bracelet" | "cufflinks"]}</span>
                </li>
              ))}
            </ul>
          </Card>
        </aside>
      </div>
    </section>
  );
}

const MATERIAL_SWATCH: Record<string, string> = {
  "silver-925": "bg-[#d9d9d9]",
  "gold-18k-yellow": "bg-[#d4b55f]",
  "gold-18k-rose": "bg-[#d8a08a]",
  "gold-18k-white": "bg-[#e9e9ea]",
  platinum: "bg-[#c7c9cc]",
};
