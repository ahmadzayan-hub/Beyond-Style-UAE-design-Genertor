"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import * as api from "@/lib/api";
import { Lang, STRINGS } from "@/lib/i18n";
import StartStep from "@/components/golden-path/StartStep";
import ConfirmStep from "@/components/golden-path/ConfirmStep";
import ApproveStep from "@/components/golden-path/ApproveStep";
import ApprovedStep from "@/components/golden-path/ApprovedStep";
import ProPanel from "@/components/golden-path/ProPanel";
import ActionBar from "@/components/golden-path/ActionBar";
import JewelryCheck, { QaReport } from "@/components/golden-path/JewelryCheck";
import type { IntegrityReport } from "@/components/golden-path/IntegrityPanel";
import type { Ladder } from "@/components/golden-path/ReadinessLadder";

// Three.js is heavy — load the 3D viewer only when its tab is opened.
const Viewer3D = dynamic(() => import("@/components/Viewer3D"), { ssr: false });

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
  const [requestId, setRequestId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState<string | null>(null);

  const [text, setText] = useState("");
  const [message, setMessage] = useState("");
  const [styleIntent, setStyleIntent] = useState<string | null>(null);
  const [scriptFamily, setScriptFamily] = useState<string | null>(null);
  const [styleCards, setStyleCards] = useState<any[]>([]);
  const [integrity, setIntegrity] = useState<IntegrityReport | null>(null);
  const [qa, setQa] = useState<QaReport | null>(null);
  const [thickness, setThickness] = useState(1.0);
  const [fidelity, setFidelity] = useState<Record<string, string>>({});
  const [ladder, setLadder] = useState<Ladder | null>(null);
  useEffect(() => {
    api.stylesCatalogue().then((r) => setStyleCards(r.styles || [])).catch(() => {});
  }, []);
  const [refFile, setRefFile] = useState<File | null>(null);
  const [refPreview, setRefPreview] = useState<string | null>(null);
  const [styleStrength, setStyleStrength] = useState(0.5);
  const [refUnderstood, setRefUnderstood] = useState(false);
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
    setApprovalLink(null);   // a link is bound to one exact version
  }
  const [studioTab, setStudioTab] = useState<"2d" | "3d" | "photoreal">("2d");
  const [previewMaterial, setPreviewMaterial] = useState("silver-925");
  const [mesh3d, setMesh3d] = useState<import("@/components/Viewer3D").Mesh3DPayload | null>(null);
  const [previewScene, setPreviewScene] = useState("studio_white");
  const [previewQuality, setPreviewQuality] = useState("DRAFT");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [studioSvg, setStudioSvg] = useState<string | null>(null);
  const [previewNote, setPreviewNote] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [proOpen, setProOpen] = useState(false);
  const [previewMode, setPreviewMode] = useState<"fit" | "actual">("fit");
  const [editParams, setEditParams] = useState<any>({});
  const [repair, setRepair] = useState<{
    available: boolean;
    options: any[];
    beforeSvg?: string;
    afterSvg?: string;
    newVersionId?: string;
    applied: boolean;
  }>({ available: false, options: [], applied: false });
  const [approveChecked, setApproveChecked] = useState(false);
  const [agreementSvg, setAgreementSvg] = useState<string | null>(null);
  const [productType, setProductType] = useState<"pendant" | "ring">("pendant");
  const [ringSize, setRingSize] = useState(52);
  const [bandHeight, setBandHeight] = useState(7.5);
  const [innerText, setInnerText] = useState("");
  const [approval, setApproval] = useState<{ approval_hash: string } | null>(null);
  const [approvalLink, setApprovalLink] = useState<{ url: string; expires_at: string } | null>(null);

  useEffect(() => {
    document.documentElement.dir = t.dir;
    document.documentElement.lang = lang;
  }, [lang, t.dir]);

  /** Accepts either a pre-localized string (for a few call sites that
   * already know the specific, more actionable message to show) or the
   * caught error itself — an api.ApiError carries a structured `code`
   * mapped to a friendly AR/EN message plus an optional request_id
   * shown as a small support detail; anything else falls back to the
   * generic UNKNOWN message rather than a raw stack trace. */
  function fail(err: string | unknown) {
    if (typeof err === "string") {
      setError(err);
      setRequestId(null);
    } else if (err instanceof api.ApiError) {
      setError(t.error_codes[err.code] || t.error_codes.UNKNOWN);
      setRequestId(err.requestId || null);
    } else {
      setError(t.error_codes.UNKNOWN);
      setRequestId(null);
    }
    setBusy(false);
    setBusyLabel(null);
  }

  async function handleStart() {
    setError(null);
    setRequestId(null);
    if (!text.trim()) return;
    setBusy(true);
    try {
      // A ring's optional inner engraving is the second line of the SAME
      // immutable source text (outer\ninner) — one confirmed text, two faces.
      const fullText =
        productType === "ring" && innerText.trim()
          ? `${text.trim()}\n${innerText.trim()}`
          : text.trim();
      const created = await api.createDesign(fullText, productType);
      setDesignId(created.design_id);
      setNormalizedText(created.normalized_text);
      setIntegrity(created.integrity || null);
      if (refFile) {
        try {
          setBusyLabel(t.uploading_label);
          const ref = await api.uploadReference(created.design_id, refFile, message || null);
          if (ref.ip_risk === "POTENTIAL_COPY_RISK") setCopyNotice(true);
          // Reference Intelligence: DesignDNA analysis (labelled source).
          try {
            setBusyLabel(t.analyzing_label);
            await api.analyzeReference(created.design_id, ref.reference_id);
            setRefUnderstood(true);
          } catch {}
          setBusyLabel(null);
        } catch (e) {
          return fail(e instanceof api.ApiError ? e : t.error_upload);
        }
      }
      await api.updateBrief(created.design_id, {
        customer_message: message || null,
        style_intent: styleIntent,
        script_family: scriptFamily,
        material_preference: previewMaterial,
        product_type: productType,
        language: lang,
        style_strength: styleStrength,
        ...(productType === "ring"
          ? { ring_size_eu: ringSize, band_height_mm: bandHeight }
          : {}),
      });
      setBusy(false);
      setStep("confirm");
    } catch (e) {
      fail(e);
    }
  }

  async function handleConfirm() {
    if (!designId || !confirmChecked) return;
    setError(null);
    setRequestId(null);
    setBusy(true);
    try {
      await api.confirmText(designId, normalizedText);
    } catch (e) {
      return fail(e instanceof api.ApiError && e.code === "ARABIC_VALIDATION_FAILED" ? t.error_mismatch : e);
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
          const svg = await api.candidateSvg(designId, card.candidate_id, previewMaterial);
          setProofs((prev) =>
            prev.map((p) => (p.candidate_id === card.candidate_id ? { ...p, svg } : p))
          );
        } catch {}
      });
    } catch (e) {
      clearInterval(ticker);
      setStep("confirm");
      fail(e);
    }
  }

  async function refreshQa(versionId: string, material: string, t_mm: number) {
    try {
      const mat = ["silver-925", "gold-18k-yellow", "gold-18k-rose", "gold-18k-white", "platinum"].includes(material) ? material : "silver-925";
      setQa(await api.jewelryQa(versionId, mat === "platinum" ? "gold-18k-white" : mat, t_mm));
    } catch {
      setQa(null);
    }
  }

  async function changeThickness(t_mm: number) {
    setThickness(t_mm);
    if (selected) refreshQa(selected.version_id, previewMaterial, t_mm);
  }

  async function changeMaterial(material: string) {
    setPreviewMaterial(material);
    if (!selected) return;
    refreshQa(selected.version_id, material, thickness);
    try {
      const svg = await api.versionSvg(selected.version_id, material);
      setHistory((h) => h.map((v, i) => (i === histIdx ? { ...v, svg } : v)));
    } catch {}
  }

  async function handleChoose(candidateId: string) {
    if (!designId) return;
    setError(null);
    setRequestId(null);
    setBusy(true);
    try {
      const sel = await api.selectCandidate(designId, candidateId);
      const [svg, full] = await Promise.all([
        api.versionSvg(sel.version_id, previewMaterial),
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
      refreshQa(sel.version_id, previewMaterial, thickness);
      const opts = await api.repairOptions(sel.version_id);
      setRepair({ available: opts.options.some((o: any) => o.available), options: opts.options, applied: false });
      setBusy(false);
      setStep("selected");
    } catch (e) {
      fail(e);
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
      "dot_style", "swash", "kashida_count", "ot_feature_set", "max_lines",
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
    } catch (e) {
      fail(e);
    }
  }

  async function handleGeneratePreview() {
    if (!selected) return;
    setBusy(true);
    setPreviewNote(null);
    try {
      const res = await api.generatePreview(selected.version_id, {
        material: previewMaterial,
        scene: previewScene,
        quality: previewQuality,
      });
      setPreviewUrl(await api.previewImageUrl(res.generation_id));
      setPreviewNote(t.ai_preview_label);
      setBusy(false);
    } catch (e: any) {
      setPreviewUrl(null);
      if (e.status === 503) {
        // Honest fallback: the deterministic studio render (same vector
        // path, metal + scene ground) stands in for the paid photoreal tier.
        await showStudioRender();
        setPreviewNote(t.preview_fallback_label);
      } else {
        setPreviewNote(t.preview_rejected);
      }
      setBusy(false);
    }
  }

  const RENDER_MATERIALS = ["silver-925", "gold-18k-yellow", "gold-18k-rose", "gold-18k-white", "platinum"];
  const RENDER_SCENES = ["studio_white", "clean_design", "luxury_black", "beyond_style_gold"];

  async function showStudioRender() {
    if (!selected) return;
    const material = RENDER_MATERIALS.includes(previewMaterial) ? previewMaterial : "silver-925";
    const scene = RENDER_SCENES.includes(previewScene) ? previewScene : "studio_white";
    try {
      const svg = await api.versionSvg(selected.version_id, material, scene);
      setStudioSvg(svg);
    } catch {
      setStudioSvg(null);
    }
  }

  async function handleApplyRepair(repairId: string) {
    if (!selected) return;
    setBusy(true);
    try {
      const rep = await api.applyRepairById(selected.version_id, repairId);
      const [beforeSvg, afterSvg] = await Promise.all([
        api.versionSvg(rep.parent_version_id),
        api.versionSvg(rep.version_id),
      ]);
      setRepair((r) => ({
        ...r,
        available: true,
        beforeSvg,
        afterSvg,
        newVersionId: rep.version_id,
        applied: false,
      }));
      setBusy(false);
    } catch (e) {
      fail(e);
    }
  }

  /** A Pro-mode vector edit landed as a new version: show it, refresh the
   *  manufacturing check and the validated repair offers for it. */
  async function afterVectorEdit(res: any) {
    const [svg, full, opts] = await Promise.all([
      api.versionSvg(res.version_id),
      api.getVersion(res.version_id),
      api.repairOptions(res.version_id),
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
    setRepair({ available: opts.options.some((o: any) => o.available), options: opts.options, applied: false });
    refreshQa(res.version_id, previewMaterial, thickness);
    if (!res.validation_passed) setError(t.edit_invalid);
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
    } catch (e) {
      fail(e);
    }
  }

  async function handleApprove() {
    if (!selected || !approveChecked) return;
    setError(null);
    setRequestId(null);
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
      try { setLadder(await api.readiness(selected.version_id)); } catch {}
      setFidelity({});
      setStep("approved");
    } catch (e) {
      fail(e instanceof api.ApiError && e.code === "ARABIC_VALIDATION_FAILED" ? t.error_mismatch : e);
    }
  }

  async function handleCreateLink() {
    if (!selected) return;
    setBusy(true);
    try {
      const res = await api.createApprovalLink(selected.version_id);
      setApprovalLink({ url: `${window.location.origin}${res.path}`, expires_at: res.expires_at });
      setBusy(false);
    } catch (e) {
      fail(e);
    }
  }

  async function handleDownload(fmt: "svg" | "dxf" | "pdf" | "png") {
    if (!selected) return;
    try {
      const verdict = await api.downloadExport(selected.version_id, fmt);
      setFidelity((f) => ({ ...f, [fmt]: verdict }));
      try { setLadder(await api.readiness(selected.version_id)); } catch {}
    } catch {
      setError(t.error_export);
      setRequestId(null);
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
          <button className="ms-3 underline" onClick={() => { setError(null); setRequestId(null); }}>
            {t.retry}
          </button>
          {requestId && (
            <p className="mt-1 text-xs text-red-800/60" data-testid="error-request-id">
              {t.support_detail} {requestId}
            </p>
          )}
        </div>
      )}

      {copyNotice && step !== "start" && (
        <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          {t.copy_risk_notice}
        </div>
      )}

      {step === "start" && (
        <StartStep
          t={t} text={text} setText={setText} message={message} setMessage={setMessage}
          refFile={refFile} setRefFile={setRefFile} refPreview={refPreview} setRefPreview={setRefPreview}
          styleStrength={styleStrength} setStyleStrength={setStyleStrength}
          styleIntent={styleIntent} setStyleIntent={setStyleIntent}
          scriptFamily={scriptFamily} setScriptFamily={setScriptFamily} styleCards={styleCards} lang={lang}
          material={previewMaterial} setMaterial={setPreviewMaterial}
          productType={productType} setProductType={setProductType}
          ringSize={ringSize} setRingSize={setRingSize} bandHeight={bandHeight} setBandHeight={setBandHeight}
          innerText={innerText} setInnerText={setInnerText}
          busy={busy} busyLabel={busyLabel} onStart={handleStart}
        />
      )}

      {step === "confirm" && (
        <ConfirmStep
          t={t} lang={lang} integrity={integrity} normalizedText={normalizedText} confirmChecked={confirmChecked}
          setConfirmChecked={setConfirmChecked} busy={busy} onConfirm={handleConfirm}
          onBack={() => setStep("start")}
        />
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
          <h2 className="mb-2 text-xl font-bold">{t.proofs_title}</h2>
          <div className="mb-3 flex flex-wrap gap-1 text-[10px]" data-testid="trust-badges">
            {refUnderstood && <span className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-800">{t.badge_ref}</span>}
            <span className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-800">{t.badge_arabic}</span>
            <span className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-800">{t.badge_mfg}</span>
            <span className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-800">{t.badge_original}</span>
          </div>
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
          <div className="flex gap-2 text-xs" data-testid="studio-tabs">
            {(["2d", "3d", "photoreal"] as const).map((tab) => (
              <button
                key={tab}
                data-testid={`tab-${tab}`}
                onClick={async () => {
                  setStudioTab(tab);
                  if (tab === "3d" && !mesh3d) {
                    try {
                      setMesh3d(await api.mesh3dPayload(selected.version_id));
                    } catch {
                      setMesh3d(null);
                    }
                  }
                }}
                className={`rounded-full border px-3 py-1 ${
                  studioTab === tab ? "border-brand-gold bg-brand-gold text-white" : "border-stone-300 bg-white"
                }`}
              >
                {tab === "2d" ? t.tab_2d : tab === "3d" ? t.tab_3d : t.tab_photoreal}
              </button>
            ))}
          </div>
          {studioTab === "2d" ? (
            <div className={`${previewMode === "actual" ? "proof-actual" : "proof-svg-large"} rounded-xl border border-stone-200 bg-white p-4`} data-testid="selected-preview">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-xs" data-testid="preview-mode">
                <span className="text-stone-500">{t.preview_mode}:</span>
                {(["fit", "actual"] as const).map((m) => (
                  <button
                    key={m}
                    data-testid={`preview-mode-${m}`}
                    onClick={() => setPreviewMode(m)}
                    className={`rounded-full border px-3 py-1 ${previewMode === m ? "border-brand-dark bg-brand-dark text-white" : "border-stone-300 bg-white"}`}
                  >
                    {m === "fit" ? t.preview_fit : t.preview_actual}
                  </button>
                ))}
              </div>
              {previewMode === "actual" && <p className="mb-2 text-[11px] text-stone-500">{t.preview_actual_note}</p>}
              {selected.svg && <div dangerouslySetInnerHTML={{ __html: selected.svg }} />}
              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(t.materials).map(([key, label]) => (
                  <button
                    key={key}
                    data-testid={`studio-material-${key}`}
                    onClick={() => changeMaterial(key)}
                    className={`rounded-full border px-3 py-1 text-xs ${
                      previewMaterial === key ? "border-brand-gold bg-brand-gold text-white" : "border-stone-300 bg-white"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <p className="mt-2 text-[11px] text-stone-500">{t.render_note}</p>
            </div>
          ) : studioTab === "3d" ? (
            <div className="flex flex-col gap-3 rounded-xl border border-stone-200 bg-white p-4" data-testid="viewer3d-panel">
              {mesh3d ? (
                <>
                  <Viewer3D payload={mesh3d} material={previewMaterial} />
                  <p className="text-sm font-medium" data-testid="viewer3d-dims">
                    {mesh3d.ring
                      ? `${t.ring_size_label}: ${mesh3d.ring.size_eu} · ${t.band_height_label}: ${mesh3d.ring.band_height_mm}`
                      : `${mesh3d.width_mm.toFixed(1)} × ${mesh3d.height_mm.toFixed(1)} mm`}
                    {" · "}
                    {t.weight_estimate}:{" "}
                    {mesh3d.weight_estimate_g[previewMaterial] != null
                      ? `${mesh3d.weight_estimate_g[previewMaterial].toFixed(2)} g`
                      : "—"}
                  </p>
                  <label className="text-xs">
                    {t.studio_material}
                    <select
                      data-testid="viewer3d-material"
                      value={previewMaterial}
                      onChange={(e) => setPreviewMaterial(e.target.value)}
                      className="mt-1 w-full rounded border border-stone-300 p-2"
                    >
                      {["silver-925", "gold-18k-yellow", "gold-18k-rose", "gold-18k-white", "platinum"].map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </label>
                  <p className="text-[11px] text-stone-500">{t.viewer3d_note}</p>
                </>
              ) : (
                <div className="h-40 w-full animate-pulse rounded bg-stone-100" />
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-3 rounded-xl border border-stone-200 bg-white p-4" data-testid="photoreal-panel">
              {previewUrl ? (
                <img src={previewUrl} alt="AI preview" className="w-full rounded-lg" data-testid="photoreal-image" />
              ) : studioSvg ? (
                <div className="proof-svg-large" data-testid="studio-render">
                  <div dangerouslySetInnerHTML={{ __html: studioSvg }} />
                </div>
              ) : (
                <div className="proof-svg-large">
                  {selected.svg && <div dangerouslySetInnerHTML={{ __html: selected.svg }} />}
                </div>
              )}
              {previewNote && (
                <p className="text-[11px] text-stone-500" data-testid="preview-note">{previewNote}</p>
              )}
              <label className="text-xs">
                {t.studio_material}
                <select
                  data-testid="preview-material"
                  value={previewMaterial}
                  onChange={(e) => setPreviewMaterial(e.target.value)}
                  className="mt-1 w-full rounded border border-stone-300 p-2"
                >
                  {["silver-925", "gold-18k-yellow", "gold-18k-rose", "gold-18k-white", "platinum", "two-tone", "enamel"].map((mm) => (
                    <option key={mm} value={mm}>{mm}</option>
                  ))}
                </select>
              </label>
              <label className="text-xs">
                {t.studio_scene}
                <select
                  data-testid="preview-scene"
                  value={previewScene}
                  onChange={(e) => setPreviewScene(e.target.value)}
                  className="mt-1 w-full rounded border border-stone-300 p-2"
                >
                  {["clean_design", "studio_white", "luxury_black", "beyond_style_gold", "on_body_neck", "on_body_ear", "on_body_hand", "on_body_wrist", "packaging", "macro_detail"].map((sc) => (
                    <option key={sc} value={sc}>{sc}</option>
                  ))}
                </select>
              </label>
              <label className="text-xs">
                {t.studio_quality}
                <select
                  data-testid="preview-quality"
                  value={previewQuality}
                  onChange={(e) => setPreviewQuality(e.target.value)}
                  className="mt-1 w-full rounded border border-stone-300 p-2"
                >
                  {["DRAFT", "STANDARD", "FINAL"].map((q) => (
                    <option key={q} value={q}>{q}</option>
                  ))}
                </select>
              </label>
              <button
                data-testid="generate-preview"
                disabled={busy}
                onClick={handleGeneratePreview}
                className="rounded-lg bg-brand-dark py-3 text-sm font-semibold text-white disabled:opacity-40"
              >
                {t.studio_generate}
              </button>
            </div>
          )}
          <div dir="auto" className="rounded-lg bg-white p-3 text-center text-2xl font-bold" data-testid="selected-text">
            {normalizedText}
          </div>

          {qa && <JewelryCheck t={t} lang={lang} report={qa} thickness={thickness} setThickness={changeThickness} />}
          {repair.available && !repair.applied && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 whitespace-pre-line" data-testid="repair-box">
              <p className="text-sm font-medium text-emerald-900">{t.improve_available}</p>
              {!repair.afterSvg ? (
                <div className="mt-2 flex flex-col gap-2" data-testid="repair-options">
                  <p className="text-xs text-emerald-900">{t.repair_choose}</p>
                  {repair.options.filter((o) => o.available).map((o) => (
                    <button
                      key={o.repair_id}
                      data-testid={`repair-preview-${o.repair_id}`}
                      disabled={busy}
                      onClick={() => handleApplyRepair(o.repair_id)}
                      className="rounded-lg bg-emerald-700 px-4 py-2 text-start text-sm font-semibold text-white disabled:opacity-40"
                    >
                      {lang === "ar" ? o.label_ar : o.label_en}
                      {o.errors_after != null && (
                        <span className="ms-2 text-xs font-normal opacity-80">
                          {t.repair_after}: {o.errors_before} → {o.errors_after}
                        </span>
                      )}
                    </button>
                  ))}
                  {repair.options.filter((o) => !o.available).map((o) => (
                    <p key={o.repair_id} className="text-[11px] text-stone-500" data-testid={`repair-unavailable-${o.repair_id}`}>
                      {t.repair_unavailable} {lang === "ar" ? o.label_ar : o.label_en} — {o.reason}
                    </p>
                  ))}
                </div>
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
                {t.edit_dot_style}
                <select
                  data-testid="select-dot-style"
                  value={editParams.dot_style ?? "round"}
                  onChange={(e) => setEditParams({ ...editParams, dot_style: e.target.value })}
                  className="mt-1 w-full rounded border border-stone-300 p-2"
                >
                  {["round", "diamond", "square", "petal"].map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label className="text-xs">
                {t.edit_swash}
                <select
                  data-testid="select-swash"
                  value={editParams.swash ?? "none"}
                  onChange={(e) => setEditParams({ ...editParams, swash: e.target.value })}
                  className="mt-1 w-full rounded border border-stone-300 p-2"
                >
                  {["none", "underline_flourish", "tail_sweep", "double_flourish"].map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label className="text-xs">
                <span className="flex justify-between">
                  <span>{t.edit_kashida}</span>
                  <span className="tabular-nums">{editParams.kashida_count ?? 0}</span>
                </span>
                <input
                  type="range"
                  data-testid="slider-kashida"
                  min={0} max={3} step={1}
                  value={editParams.kashida_count ?? 0}
                  onChange={(e) => setEditParams({ ...editParams, kashida_count: Number(e.target.value) })}
                  className="w-full accent-brand-gold"
                />
              </label>
              <label className="text-xs">
                {t.edit_lines}
                <select
                  data-testid="select-lines"
                  value={editParams.max_lines ?? 1}
                  onChange={(e) => setEditParams({ ...editParams, max_lines: Number(e.target.value) })}
                  className="mt-1 w-full rounded border border-stone-300 p-2"
                >
                  {[1, 2, 3, 4].map((c) => (
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
                  {["top", "left_right", "upper_left_right", "none"].map((c) => (
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
            data-testid="pro-toggle"
            onClick={() => setProOpen(!proOpen)}
            className="rounded-xl border border-stone-400 p-3 text-sm font-semibold text-stone-700"
          >
            {t.pro_open}
          </button>
          {proOpen && (
            <ProPanel
              t={t} lang={lang} versionId={selected.version_id} currentSvg={selected.svg} busy={busy}
              onApplied={afterVectorEdit} onError={(m) => setError(m)}
            />
          )}

          <button
            data-testid="to-approve"
            disabled={busy || !selected.validation_passed}
            onClick={async () => {
              setStep("approve");
              // The customer approves the DIMENSIONED artifact; fall back
              // to the plain proof if the endpoint is unreachable.
              try {
                setAgreementSvg(await api.agreementProofSvg(selected.version_id));
              } catch {
                setAgreementSvg(null);
              }
            }}
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
        <ApproveStep
          t={t} lang={lang} agreementSvg={agreementSvg} selected={selected}
          normalizedText={normalizedText} approveChecked={approveChecked}
          setApproveChecked={setApproveChecked} busy={busy} onApprove={handleApprove}
          onBack={() => setStep("selected")}
          link={approvalLink} onCreateLink={handleCreateLink}
        />
      )}

      {step === "approved" && selected && approval && (
        <ApprovedStep t={t} selected={selected} approval={approval} onDownload={handleDownload}
                      lang={lang} fidelity={fidelity} ladder={ladder} />
      )}

      {/* Mobile-first primary action: one thumb-reachable button per step. */}
      {step === "start" && (
        <ActionBar label={t.bar_start} testId="bar-start" disabled={busy || (!text.trim() && !refFile)} onClick={handleStart} />
      )}
      {step === "confirm" && (
        <ActionBar label={t.bar_confirm} testId="bar-confirm" disabled={busy || !confirmChecked} onClick={handleConfirm} />
      )}
      {step === "selected" && selected && (
        <ActionBar
          label={t.bar_approve} testId="bar-approve" disabled={busy || !selected.validation_passed}
          onClick={async () => {
            setStep("approve");
            try {
              setAgreementSvg(await api.agreementProofSvg(selected.version_id));
            } catch {
              setAgreementSvg(null);
            }
          }}
        />
      )}
      {step === "approved" && selected && approval && (
        <ActionBar label={t.bar_download} testId="bar-download" disabled={busy} onClick={() => handleDownload("svg")} />
      )}
    </main>
  );
}
