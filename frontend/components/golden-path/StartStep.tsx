"use client";

import { useRef } from "react";
import type { Strings } from "./types";

/** Step 1 of the Golden Path: customer text, optional reference image with
 * style strength + message, product choice (ring fields), style intent.
 * Extracted verbatim from app/page.tsx — every data-testid is unchanged. */
export interface StartStepProps {
  t: Strings;
  text: string; setText: (v: string) => void;
  message: string; setMessage: (v: string) => void;
  refFile: File | null; setRefFile: (f: File | null) => void;
  refPreview: string | null; setRefPreview: (v: string | null) => void;
  styleStrength: number; setStyleStrength: (v: number) => void;
  styleIntent: string | null; setStyleIntent: (v: string | null) => void;
  productType: "pendant" | "ring"; setProductType: (v: "pendant" | "ring") => void;
  ringSize: number; setRingSize: (v: number) => void;
  bandHeight: number; setBandHeight: (v: number) => void;
  innerText: string; setInnerText: (v: string) => void;
  busy: boolean; busyLabel: string | null;
  onStart: () => void;
}

export default function StartStep({
  t, text, setText, message, setMessage, refFile, setRefFile, refPreview, setRefPreview,
  styleStrength, setStyleStrength, styleIntent, setStyleIntent, productType, setProductType,
  ringSize, setRingSize, bandHeight, setBandHeight, innerText, setInnerText,
  busy, busyLabel, onStart,
}: StartStepProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  return (
    <section className="flex flex-col gap-5">
      <div>
        <h2 className="text-2xl font-bold">{t.start_title}</h2>
        <p className="mt-1 text-sm text-stone-500">{t.start_subtitle}</p>
      </div>
      <input
        data-testid="text-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={t.text_placeholder}
        className="rounded-xl border border-stone-300 bg-white p-4 text-lg focus:border-brand-gold focus:outline-none"
      />
      <div className="rounded-xl border border-dashed border-stone-300 bg-white p-4">
        <button
          onClick={() => fileInput.current?.click()}
          className="w-full text-start text-sm font-medium text-brand-gold"
          data-testid="upload-button"
        >
          {t.upload_reference}
        </button>
        <p className="mt-1 text-xs text-stone-400">{t.upload_hint}</p>
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
          <img
            src={refPreview}
            alt="reference"
            data-testid="reference-preview"
            className="mt-3 max-h-40 rounded-lg object-contain"
          />
        )}
        {refFile && (
          <label className="mt-3 block text-xs">
            <span className="flex justify-between">
              <span>{t.strength_original}</span>
              <span className="font-medium">{t.style_strength}</span>
              <span>{t.strength_similar}</span>
            </span>
            <input
              type="range" data-testid="style-strength"
              min={0} max={1} step={0.1} value={styleStrength}
              onChange={(e) => setStyleStrength(Number(e.target.value))}
              className="w-full accent-brand-gold"
            />
          </label>
        )}
        {refFile && (
          <textarea
            data-testid="message-input"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={t.message_placeholder}
            className="mt-3 w-full rounded-lg border border-stone-200 p-3 text-sm"
            rows={2}
          />
        )}
      </div>
      <div>
        <p className="mb-2 text-sm font-medium">{t.product_label}</p>
        <div className="flex flex-wrap gap-2">
          {(["pendant", "ring"] as const).map((p) => (
            <button
              key={p}
              data-testid={`product-${p}`}
              onClick={() => setProductType(p)}
              className={`rounded-full border px-4 py-2 text-sm ${
                productType === p
                  ? "border-brand-gold bg-brand-gold text-white"
                  : "border-stone-300 bg-white"
              }`}
            >
              {t.products[p]}
            </button>
          ))}
        </div>
        {productType === "ring" && (
          <div className="mt-3 flex flex-wrap gap-3">
            <label className="flex-1 text-xs">
              {t.ring_size_label}
              <select
                data-testid="ring-size"
                value={ringSize}
                onChange={(e) => setRingSize(Number(e.target.value))}
                className="mt-1 w-full rounded border border-stone-300 p-2"
              >
                {Array.from({ length: 27 }, (_, i) => 44 + i).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex-1 text-xs">
              {t.inner_engraving_label}
              <input
                data-testid="inner-text-input"
                value={innerText}
                onChange={(e) => setInnerText(e.target.value)}
                placeholder={t.inner_engraving_hint}
                className="mt-1 w-full rounded border border-stone-300 p-2"
              />
            </label>
            <label className="flex-1 text-xs">
              {t.band_height_label}
              <select
                data-testid="band-height"
                value={bandHeight}
                onChange={(e) => setBandHeight(Number(e.target.value))}
                className="mt-1 w-full rounded border border-stone-300 p-2"
              >
                {[5.5, 6.5, 7.5, 8.5].map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
      </div>
      <div>
        <p className="mb-2 text-sm font-medium">{t.style_label}</p>
        <div className="flex flex-wrap gap-2">
          {Object.entries(t.styles).map(([key, label]) => (
            <button
              key={key}
              data-testid={`style-${key}`}
              onClick={() => setStyleIntent(styleIntent === key ? null : key)}
              className={`rounded-full border px-4 py-2 text-sm ${
                styleIntent === key
                  ? "border-brand-gold bg-brand-gold text-white"
                  : "border-stone-300 bg-white"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {busyLabel && (
        <p className="text-center text-sm text-brand-dark/70" data-testid="busy-label">
          {busyLabel}
        </p>
      )}
      <button
        data-testid="start-continue"
        disabled={!text.trim() || busy}
        onClick={onStart}
        className="rounded-xl bg-brand-dark p-4 text-lg font-semibold text-white disabled:opacity-40"
      >
        {t.continue}
      </button>
    </section>
  );
}
