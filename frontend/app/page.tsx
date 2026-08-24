"use client";

import { useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import { Lang, STRINGS } from "@/lib/i18n";

type Step =
  | "start"
  | "confirm"
  | "generating"
  | "proofs"
  | "selected"
  | "approve"
  | "approved";

interface ProofCard {
  candidate_id: string;
  rank: number;
  name: string;
  composition: string;
  width_mm: number;
  height_mm: number;
  svg?: string;
}

export default function GoldenPathPage() {
  const [lang, setLang] = useState<Lang>("ar");
  const t = STRINGS[lang];
  const [step, setStep] = useState<Step>("start");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [text, setText] = useState("");
  const [message, setMessage] = useState("");
  const [styleIntent, setStyleIntent] = useState<string | null>(null);
  const [refFile, setRefFile] = useState<File | null>(null);
  const [refPreview, setRefPreview] = useState<string | null>(null);
  const [copyNotice, setCopyNotice] = useState(false);

  const [designId, setDesignId] = useState<string | null>(null);
  const [normalizedText, setNormalizedText] = useState("");
  const [confirmChecked, setConfirmChecked] = useState(false);
  const [genStep, setGenStep] = useState(0);
  const [proofs, setProofs] = useState<ProofCard[]>([]);
  interface SelectedVersion {
    version_id: string;
    version_number: number;
    source_text_sha256: string;
    geometry_hash: string;
    validation_passed: boolean;
    recipe: any;
    svg?: string;
  }
  const [history, setHistory] = useState<SelectedVersion[]>([]);
  const [histIdx, setHistIdx] = useState(-1);
  const selected = histIdx >= 0 ? history[histIdx] : null;
  function pushVersion(v: SelectedVersion) {
    setHistory((h) => [...h.slice(0, histIdx + 1), v]);
    setHistIdx((i) => i + 1);
  }
  const [editOpen, setEditOpen] = useState(false);
  const [editParams, setEditParams] = useState<any>({});
  const [repair, setRepair] = useState<{
    available: boolean;
    beforeSvg?: string;
    afterSvg?: string;
    newVersionId?: string;
    applied: boolean;
  }>({ available: false, applied: false });
  const [approveChecked, setApproveChecked] = useState(false);
  const [approval, setApproval] = useState<{ approval_hash: string } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    document.documentElement.dir = t.dir;
    document.documentElement.lang = lang;
  }, [lang, t.dir]);

  function fail(msg: string) {
    setError(msg);
    setBusy(false);
  }

  async function handleStart() {
    setError(null);
    if (!text.trim()) return;
    setBusy(true);
    try {
      const created = await api.createDesign(text.trim());
      setDesignId(created.design_id);
      setNormalizedText(created.normalized_text);
      if (refFile) {
        try {
          const ref = await api.uploadReference(created.design_id, refFile, message || null);
          if (ref.ip_risk === "POTENTIAL_COPY_RISK") setCopyNotice(true);
        } catch {
          return fail(t.error_upload);
        }
      }
      await api.updateBrief(created.design_id, {
        customer_message: message || null,
        style_intent: styleIntent,
        product_type: "pendant",
        language: lang,
      });
      setBusy(false);
      setStep("confirm");
    } catch {
      fail(t.error_generation);
    }
  }

  async function handleConfirm() {
    if (!designId || !confirmChecked) return;
    setError(null);
    setBusy(true);
    try {
      await api.confirmText(designId, normalizedText);
    } catch (e: any) {
      return fail(e.status === 422 ? t.error_mismatch : t.error_generation);
    }
    setStep("generating");
    setGenStep(0);
    const ticker = setInterval(
      () => setGenStep((s) => Math.min(s + 1, t.generating_steps.length - 1)),
      900
    );
    try {
      const gen = await api.generateCandidates(designId);
      clearInterval(ticker);
      const cards: ProofCard[] = gen.top.map((c: any) => ({
        candidate_id: c.candidate_id,
        rank: c.rank,
        name: c.name,
        composition: c.composition,
        width_mm: c.width_mm,
        height_mm: c.height_mm,
      }));
      setProofs(cards);
      setBusy(false);
      setStep("proofs");
      // Progressive vector loading — cards render as SVGs arrive.
      cards.forEach(async (card) => {
        try {
          const svg = await api.candidateSvg(designId, card.candidate_id);
          setProofs((prev) =>
            prev.map((p) => (p.candidate_id === card.candidate_id ? { ...p, svg } : p))
          );
        } catch {}
      });
    } catch {
      clearInterval(ticker);
      setStep("confirm");
      fail(t.error_generation);
    }
  }

  async function handleChoose(candidateId: string) {
    if (!designId) return;
    setError(null);
    setBusy(true);
    try {
      const sel = await api.selectCandidate(designId, candidateId);
      const [svg, full] = await Promise.all([
        api.versionSvg(sel.version_id),
        api.getVersion(sel.version_id),
      ]);
      const v = {
        version_id: sel.version_id,
        version_number: sel.version_number,
        source_text_sha256: sel.source_text_sha256,
        geometry_hash: sel.geometry_hash,
        validation_passed: true,
        recipe: full.recipe,
        svg,
      };
      setHistory([v]);
      setHistIdx(0);
      setEditParams({ ...full.recipe });
      const opts = await api.repairOptions(sel.version_id);
      setRepair({ available: opts.options.length > 0, applied: false });
      setBusy(false);
      setStep("selected");
    } catch {
      fail(t.error_generation);
    }
  }

  async function applyCopilotEdit() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    const overrides: any = {};
    for (const k of [
      "stroke_delta_mm", "letter_spacing_mm", "x_scale", "y_scale",
      "target_height_mm", "composition", "loops", "dot_strategy",
    ]) {
      if (editParams[k] !== undefined && editParams[k] !== selected.recipe[k]) {
        overrides[k] = editParams[k];
      }
    }
    if (Object.keys(overrides).length === 0) {
      setBusy(false);
      return;
    }
    try {
      const res = await api.editVersion(selected.version_id, overrides, "copilot edit");
      const [svg, full] = await Promise.all([
        api.versionSvg(res.version_id),
        api.getVersion(res.version_id),
      ]);
      pushVersion({
        version_id: res.version_id,
        version_number: res.version_number,
        source_text_sha256: res.source_text_sha256,
        geometry_hash: res.geometry_hash,
        validation_passed: res.validation_passed,
        recipe: full.recipe,
        svg,
      });
      if (!res.validation_passed) setError(t.edit_invalid);
      setBusy(false);
    } catch {
      fail(t.error_generation);
    }
  }

  async function handleApplyRepair() {
    if (!selected) return;
    setBusy(true);
    try {
      const rep = await api.applyRepair(selected.version_id);
      const [beforeSvg, afterSvg] = await Promise.all([
        api.versionSvg(rep.parent_version_id),
        api.versionSvg(rep.version_id),
      ]);
      setRepair({
        available: true,
        beforeSvg,
        afterSvg,
        newVersionId: rep.version_id,
        applied: false,
      });
      setBusy(false);
    } catch {
      fail(t.error_generation);
    }
  }

  async function acceptRepairVersion() {
    if (!repair.newVersionId) return;
    setBusy(true);
    try {
      const v = await api.getVersion(repair.newVersionId);
      pushVersion({
        version_id: v.version_id,
        version_number: v.version_number,
        source_text_sha256: v.source_text_sha256,
        geometry_hash: v.geometry_hash,
        validation_passed: v.validation_passed,
        recipe: v.recipe,
        svg: repair.afterSvg,
      });
      setRepair((r) => ({ ...r, applied: true }));
      setBusy(false);
    } catch {
      fail(t.error_generation);
    }
  }

  async function handleApprove() {
    if (!selected || !approveChecked) return;
    setError(null);
    setBusy(true);
    try {
      const res = await api.approveVersion(
        selected.version_id,
        normalizedText,
        selected.source_text_sha256,
        selected.geometry_hash
      );
      setApproval(res);
      setBusy(false);
      setStep("approved");
    } catch (e: any) {
      fail(e.status === 422 ? t.error_mismatch : t.error_generation);
    }
  }

  async function handleDownload(fmt: "svg" | "dxf") {
    if (!selected) return;
    try {
      await api.downloadExport(selected.version_id, fmt);
    } catch {
      setError(t.error_export);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-lg flex-col px-4 pb-24 pt-6">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="font-serif text-xl font-bold tracking-tight text-brand-gold">
          BEYOND STYLE
        </h1>
        <button
          onClick={() => setLang(lang === "ar" ? "en" : "ar")}
          className="rounded-full border border-brand-gold px-3 py-1 text-sm"
          data-testid="lang-toggle"
        >
          {lang === "ar" ? "English" : "عربي"}
        </button>
      </header>

      {error && (
        <div
          role="alert"
          data-testid="error-banner"
          className="mb-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800"
        >
          {error}
          <button className="ms-3 underline" onClick={() => setError(null)}>
            {t.retry}
          </button>
        </div>
      )}

      {copyNotice && step !== "start" && (
        <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          {t.copy_risk_notice}
        </div>
      )}

      {step === "start" && (
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
          <button
            data-testid="start-continue"
            disabled={!text.trim() || busy}
            onClick={handleStart}
            className="rounded-xl bg-brand-dark p-4 text-lg font-semibold text-white disabled:opacity-40"
          >
            {t.continue}
          </button>
        </section>
      )}

      {step === "confirm" && (
        <section className="flex flex-col gap-5">
          <h2 className="text-xl font-bold">{t.confirm_title}</h2>
          <div
            data-testid="confirm-text-display"
            dir="auto"
            className="rounded-xl border-2 border-brand-gold bg-white p-6 text-center text-4xl font-bold"
          >
            {normalizedText}
          </div>
          <p className="text-sm text-stone-500">{t.confirm_hint}</p>
          <label className="flex items-center gap-3 text-sm font-medium">
            <input
              type="checkbox"
              data-testid="confirm-checkbox"
              checked={confirmChecked}
              onChange={(e) => setConfirmChecked(e.target.checked)}
              className="h-5 w-5 accent-brand-gold"
            />
            {t.confirm_exact}
          </label>
          <button
            data-testid="confirm-continue"
            disabled={!confirmChecked || busy}
            onClick={handleConfirm}
            className="rounded-xl bg-brand-dark p-4 text-lg font-semibold text-white disabled:opacity-40"
          >
            {t.continue}
          </button>
          <button className="text-sm text-stone-400" onClick={() => setStep("start")}>
            {t.back}
          </button>
        </section>
      )}

      {step === "generating" && (
        <section className="flex flex-col items-center gap-6 pt-16" data-testid="generating">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-brand-gold border-t-transparent" />
          <p className="text-lg font-medium">{t.generating}</p>
          <ol className="text-sm text-stone-500">
            {t.generating_steps.map((s, i) => (
              <li key={s} className={i <= genStep ? "font-semibold text-brand-dark" : ""}>
                {i <= genStep ? "● " : "○ "}
                {s}
              </li>
            ))}
          </ol>
        </section>
      )}

      {step === "proofs" && (
        <section>
          <h2 className="mb-4 text-xl font-bold">{t.proofs_title}</h2>
          <div className="grid grid-cols-2 gap-3" data-testid="proof-grid">
            {proofs.map((p) => (
              <div
                key={p.candidate_id}
                data-testid="proof-card"
                className="flex flex-col rounded-xl border border-stone-200 bg-white p-3"
              >
                <div className="proof-svg flex min-h-[100px] items-center justify-center">
                  {p.svg ? (
                    <div dangerouslySetInnerHTML={{ __html: p.svg }} />
                  ) : (
                    <div className="h-16 w-full animate-pulse rounded bg-stone-100" />
                  )}
                </div>
                <p className="mt-2 text-xs font-semibold">
                  {p.rank}. {p.name}
                </p>
                <p className="text-[10px] text-emerald-700">{t.mfg_ok}</p>
                <button
                  data-testid={`choose-${p.rank}`}
                  disabled={busy}
                  onClick={() => handleChoose(p.candidate_id)}
                  className="mt-2 rounded-lg bg-brand-gold py-2 text-sm font-semibold text-white disabled:opacity-40"
                >
                  {t.choose}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {step === "selected" && selected && (
        <section className="flex flex-col gap-4">
          <h2 className="text-xl font-bold">{t.selected_title}</h2>
          <div className="proof-svg-large rounded-xl border border-stone-200 bg-white p-4" data-testid="selected-preview">
            {selected.svg && <div dangerouslySetInnerHTML={{ __html: selected.svg }} />}
          </div>
          <div dir="auto" className="rounded-lg bg-white p-3 text-center text-2xl font-bold" data-testid="selected-text">
            {normalizedText}
          </div>

          {repair.available && !repair.applied && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4" data-testid="repair-box">
              <p className="text-sm font-medium text-emerald-900">{t.improve_available}</p>
              {!repair.afterSvg ? (
                <button
                  data-testid="repair-preview"
                  disabled={busy}
                  onClick={handleApplyRepair}
                  className="mt-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
                >
                  {t.apply_fix}
                </button>
              ) : (
                <div className="mt-3">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <p className="text-xs text-stone-500">{t.before}</p>
                      <div className="proof-svg rounded bg-white p-2" dangerouslySetInnerHTML={{ __html: repair.beforeSvg! }} />
                    </div>
                    <div>
                      <p className="text-xs text-stone-500">{t.after}</p>
                      <div className="proof-svg rounded bg-white p-2" dangerouslySetInnerHTML={{ __html: repair.afterSvg! }} />
                    </div>
                  </div>
                  <div className="mt-3 flex gap-2">
                    <button
                      data-testid="repair-accept"
                      onClick={acceptRepairVersion}
                      className="flex-1 rounded-lg bg-emerald-700 py-2 text-sm font-semibold text-white"
                    >
                      {t.apply_fix}
                    </button>
                    <button
                      data-testid="repair-keep"
                      onClick={() => setRepair((r) => ({ ...r, applied: true }))}
                      className="flex-1 rounded-lg border border-stone-300 py-2 text-sm"
                    >
                      {t.keep_original}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="flex items-center justify-between rounded-lg bg-white p-2 text-sm" data-testid="version-bar">
            <span>
              {t.version_label} <b data-testid="current-version">{selected.version_number}</b>
              {!selected.validation_passed && " ⚠"}
            </span>
            <span className="flex gap-2">
              <button
                data-testid="undo"
                disabled={histIdx <= 0 || busy}
                onClick={() => { setHistIdx(histIdx - 1); setEditParams({ ...history[histIdx - 1].recipe }); }}
                className="rounded border border-stone-300 px-3 py-1 disabled:opacity-30"
              >
                {t.undo}
              </button>
              <button
                data-testid="redo"
                disabled={histIdx >= history.length - 1 || busy}
                onClick={() => { setHistIdx(histIdx + 1); setEditParams({ ...history[histIdx + 1].recipe }); }}
                className="rounded border border-stone-300 px-3 py-1 disabled:opacity-30"
              >
                {t.redo}
              </button>
            </span>
          </div>

          <button
            data-testid="edit-toggle"
            onClick={() => setEditOpen(!editOpen)}
            className="rounded-xl border border-brand-gold p-3 text-sm font-semibold text-brand-gold"
          >
            {t.edit_open}
          </button>

          {editOpen && (
            <div className="flex flex-col gap-3 rounded-xl border border-stone-200 bg-white p-4" data-testid="copilot-panel">
              <p className="text-sm font-bold">{t.edit_title}</p>
              {([
                ["stroke_delta_mm", t.edit_thickness, 0, 0.5, 0.01],
                ["letter_spacing_mm", t.edit_spacing, -0.3, 1.5, 0.05],
                ["x_scale", t.edit_width, 0.8, 1.3, 0.01],
                ["y_scale", t.edit_height_scale, 0.8, 1.4, 0.01],
                ["target_height_mm", t.edit_size, 8, 20, 0.5],
              ] as [string, string, number, number, number][]).map(([key, label, min, max, step_]) => (
                <label key={key} className="text-xs">
                  <span className="flex justify-between">
                    <span>{label}</span>
                    <span className="tabular-nums">{Number(editParams[key] ?? 0).toFixed(2)}</span>
                  </span>
                  <input
                    type="range"
                    data-testid={`slider-${key}`}
                    min={min} max={max} step={step_}
                    value={editParams[key] ?? 0}
                    onChange={(e) => setEditParams({ ...editParams, [key]: Number(e.target.value) })}
                    className="w-full accent-brand-gold"
                  />
                </label>
              ))}
              <label className="text-xs">
                {t.edit_composition}
                <select
                  data-testid="select-composition"
                  value={editParams.composition ?? "bare"}
                  onChange={(e) => setEditParams({ ...editParams, composition: e.target.value })}
                  className="mt-1 w-full rounded border border-stone-300 p-2"
                >
                  {["bare", "baseline_bar", "underline_bar", "top_bar", "plate_oval", "plate_rect", "frame_circle", "frame_rect"].map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label className="text-xs">
                {t.edit_loops}
                <select
                  data-testid="select-loops"
                  value={editParams.loops ?? "top"}
                  onChange={(e) => setEditParams({ ...editParams, loops: e.target.value })}
                  className="mt-1 w-full rounded border border-stone-300 p-2"
                >
                  {["top", "left_right", "none"].map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </label>
              <button
                data-testid="apply-edit"
                disabled={busy}
                onClick={applyCopilotEdit}
                className="rounded-lg bg-brand-dark py-3 text-sm font-semibold text-white disabled:opacity-40"
              >
                {t.edit_apply}
              </button>
            </div>
          )}

          <button
            data-testid="to-approve"
            disabled={busy || !selected.validation_passed}
            onClick={() => setStep("approve")}
            className="rounded-xl bg-brand-dark p-4 text-lg font-semibold text-white disabled:opacity-40"
          >
            {t.continue}
          </button>
          <button className="text-sm text-stone-400" onClick={() => setStep("proofs")}>
            {t.back}
          </button>
        </section>
      )}

      {step === "approve" && selected && (
        <section className="flex flex-col gap-5">
          <h2 className="text-xl font-bold">{t.approve_title}</h2>
          <div className="proof-svg-large rounded-xl border border-stone-200 bg-white p-4">
            {selected.svg && <div dangerouslySetInnerHTML={{ __html: selected.svg }} />}
          </div>
          <div
            data-testid="approve-text-display"
            dir="auto"
            className="rounded-xl border-2 border-brand-gold bg-white p-5 text-center text-3xl font-bold"
          >
            {normalizedText}
          </div>
          <label className="flex items-center gap-3 rounded-lg bg-white p-4 text-sm font-medium">
            <input
              type="checkbox"
              data-testid="approve-checkbox"
              checked={approveChecked}
              onChange={(e) => setApproveChecked(e.target.checked)}
              className="h-5 w-5 accent-brand-gold"
            />
            <span>
              {t.approve_statement}
              <br />
              <span className="text-xs text-stone-400">
                {lang === "ar" ? STRINGS.en.approve_statement : STRINGS.ar.approve_statement}
              </span>
            </span>
          </label>
          <button
            data-testid="approve-button"
            disabled={!approveChecked || busy}
            onClick={handleApprove}
            className="rounded-xl bg-brand-dark p-4 text-lg font-semibold text-white disabled:opacity-40"
          >
            {t.approve_btn}
          </button>
          <button className="text-sm text-stone-400" onClick={() => setStep("selected")}>
            {t.back}
          </button>
        </section>
      )}

      {step === "approved" && selected && approval && (
        <section className="flex flex-col gap-5" data-testid="approved">
          <h2 className="text-2xl font-bold text-emerald-700">{t.approved_title}</h2>
          <div className="proof-svg-large rounded-xl border border-stone-200 bg-white p-4">
            {selected.svg && <div dangerouslySetInnerHTML={{ __html: selected.svg }} />}
          </div>
          <div className="rounded-lg bg-white p-4 text-sm">
            <p>
              {t.approved_version}: <b data-testid="locked-version">{selected.version_number}</b>
            </p>
            <p className="mt-1 break-all text-[10px] text-stone-400" data-testid="approval-hash">
              {approval.approval_hash}
            </p>
          </div>
          <div className="flex gap-3">
            <button
              data-testid="download-svg"
              onClick={() => handleDownload("svg")}
              className="flex-1 rounded-xl border border-brand-gold p-3 font-semibold text-brand-gold"
            >
              {t.download_svg}
            </button>
            <button
              data-testid="download-dxf"
              onClick={() => handleDownload("dxf")}
              className="flex-1 rounded-xl bg-brand-gold p-3 font-semibold text-white"
            >
              {t.download_dxf}
            </button>
          </div>
          <button
            disabled
            title="coming soon"
            data-testid="make-it-disabled"
            className="rounded-xl bg-stone-300 p-4 text-lg font-semibold text-stone-500"
          >
            {t.make_it}
          </button>
        </section>
      )}
    </main>
  );
}
