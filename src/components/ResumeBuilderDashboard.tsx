import { useEffect, useState } from "react";
import type { User } from "../types";
import type { ResumeBuilderFlowState } from "../lib/resumeBuilderFlow";
import {
  DEFAULT_RESUME_STYLE,
  exportResumePdf,
  getResume,
  listResumeStyles,
  listResumeTemplates,
  previewResumePdf,
  saveResumeStyle,
  selectResumeTemplate,
  suggestResumeStyle,
  type ResumeStyle,
  type ResumeStyleOptions,
  type ResumeTemplate,
} from "../lib/resumeBuilderApi";

/** Shown if the style list cannot be loaded; mirrors the agent's own list. */
const FALLBACK_STYLE_OPTIONS: ResumeStyleOptions = {
  font_families: [
    { id: "template", label: "Template default" },
    { id: "carlito", label: "Carlito (Calibri style)" },
    { id: "helvetica", label: "Helvetica (Arial style)" },
    { id: "lato", label: "Lato" },
    { id: "open-sans", label: "Open Sans" },
    { id: "times", label: "Times (classic serif)" },
    { id: "liberation-serif", label: "Liberation Serif (Times New Roman style)" },
  ],
  font_scales: [0.9, 0.95, 1, 1.05, 1.1, 1.15, 1.2].map((value) => ({ value, label: `${Math.round(value * 100)}%` })),
  line_spacings: [{ value: 0.9, label: "Compact" }, { value: 1, label: "Standard" }, { value: 1.15, label: "Relaxed" }, { value: 1.3, label: "Spacious" }],
  default: DEFAULT_RESUME_STYLE,
};

function asStyle(value: unknown): ResumeStyle {
  const raw = (value && typeof value === "object" ? value : {}) as Partial<ResumeStyle>;
  return {
    font_family: typeof raw.font_family === "string" ? raw.font_family : DEFAULT_RESUME_STYLE.font_family,
    font_scale: typeof raw.font_scale === "number" ? raw.font_scale : DEFAULT_RESUME_STYLE.font_scale,
    line_spacing: typeof raw.line_spacing === "number" ? raw.line_spacing : DEFAULT_RESUME_STYLE.line_spacing,
  };
}

export default function ResumeBuilderDashboard({ user, state, onClose }: { user: User; state: ResumeBuilderFlowState; onClose: () => void }) {
  const experienceLevel = state.draft?.experienceLevel;
  const pagePlan = experienceLevel === "experienced" ? "Up to 2 pages" : experienceLevel === "fresher" ? "1 page" : undefined;
  const [templates, setTemplates] = useState<ResumeTemplate[]>([]);
  const [templateChoice, setTemplateChoice] = useState(state.templateChoice || "steady-form");
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const [savedResume, setSavedResume] = useState<Record<string, unknown>>();
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewError, setPreviewError] = useState("");
  const [styleOptions, setStyleOptions] = useState<ResumeStyleOptions>(FALLBACK_STYLE_OPTIONS);
  const [style, setStyle] = useState<ResumeStyle>(DEFAULT_RESUME_STYLE);
  const [styleError, setStyleError] = useState("");
  const [suggestion, setSuggestion] = useState<{ style: ResumeStyle; reason: string }>();
  const [suggesting, setSuggesting] = useState(false);
  useEffect(() => { void listResumeTemplates().then(setTemplates).catch(() => setTemplates([])); }, []);
  useEffect(() => { void listResumeStyles().then(setStyleOptions).catch(() => setStyleOptions(FALLBACK_STYLE_OPTIONS)); }, []);
  useEffect(() => {
    if (!state.resumeId) return;
    void getResume(user.id, state.resumeId)
      .then((resume) => {
        setSavedResume(resume);
        if (typeof resume.template_choice === "string" && resume.template_choice) setTemplateChoice(resume.template_choice);
        setStyle(asStyle(resume.style_settings));
      })
      .catch(() => { setSavedResume(undefined); });
  }, [state.resumeId, user.id]);
  useEffect(() => {
    if (!savedResume) return;
    let active = true;
    let url = "";
    setPreviewUrl("");
    setPreviewError("");
    void previewResumePdf(user.id, savedResume, templateChoice, style)
      .then((blob) => {
        if (!active) return;
        url = URL.createObjectURL(blob);
        setPreviewUrl(url);
      })
      .catch((error) => { if (active) setPreviewError((error as Error).message || "Resume preview failed."); });
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [savedResume, templateChoice, style, user.id]);
  async function chooseTemplate(value: string) {
    if (!state.resumeId) return;
    setSavingTemplate(true);
    try {
      await selectResumeTemplate(user.id, state.resumeId, value);
      setTemplateChoice(value);
      setSavedResume((current) => current ? { ...current, template_choice: value } : current);
    } finally { setSavingTemplate(false); }
  }
  /** Shows the new style straight away and saves it, so the download matches. */
  async function changeStyle(next: ResumeStyle) {
    if (!state.resumeId) return;
    const previous = style;
    setStyle(next);
    setStyleError("");
    try {
      await saveResumeStyle(user.id, state.resumeId, next);
    } catch (error) {
      setStyle(previous);
      setStyleError(`That style could not be saved: ${(error as Error).message || "please try again."}`);
    }
  }
  async function suggestStyle() {
    if (!savedResume || suggesting) return;
    setSuggesting(true);
    setStyleError("");
    try {
      const result = await suggestResumeStyle(user.id, savedResume, templateChoice);
      setSuggestion({ style: asStyle(result.style), reason: result.reason });
    } catch (error) {
      setStyleError(`No suggestion right now: ${(error as Error).message || "please try again."}`);
    } finally {
      setSuggesting(false);
    }
  }
  function describe(value: ResumeStyle) {
    const family = styleOptions.font_families.find((option) => option.id === value.font_family)?.label || value.font_family;
    const spacing = styleOptions.line_spacings.find((option) => option.value === value.line_spacing)?.label || value.line_spacing;
    return `${family} · ${Math.round(value.font_scale * 100)}% size · ${spacing} spacing`;
  }
  async function download() {
    if (!state.resumeId || downloading) return;
    setDownloading(true);
    setDownloadError("");
    try {
      const { blob, filename } = await exportResumePdf(user.id, state.resumeId, templateChoice, style);
      if (!blob.size) throw new Error("The generated PDF was empty. Please try again.");
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      link.remove();
      // Chrome reads Blob URLs asynchronously; immediate revocation can
      // cancel the download before that read starts.
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1_000);
    } catch (error) {
      setDownloadError((error as Error).message || "PDF download failed. Please try again.");
    } finally {
      setDownloading(false);
    }
  }
  const styleControls = state.resumeId && savedResume && (
    <section className="dashboard-card resume-style-controls" aria-label="Resume style">
      <span>Font &amp; spacing</span>
      <label>Font<select value={style.font_family} disabled={downloading} onChange={(event) => void changeStyle({ ...style, font_family: event.target.value })}>{styleOptions.font_families.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
      <label>Font size<select value={style.font_scale} disabled={downloading} onChange={(event) => void changeStyle({ ...style, font_scale: Number(event.target.value) })}>{styleOptions.font_scales.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
      <label>Line spacing<select value={style.line_spacing} disabled={downloading} onChange={(event) => void changeStyle({ ...style, line_spacing: Number(event.target.value) })}>{styleOptions.line_spacings.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
      <button type="button" className="option-btn" disabled={suggesting || downloading} onClick={() => void suggestStyle()}>{suggesting ? "Thinking…" : "✨ Suggest a professional style"}</button>
      {suggestion && <div className="resume-style-suggestion" role="status">
        <strong>{describe(suggestion.style)}</strong>
        <p>{suggestion.reason}</p>
        <button type="button" className="option-btn" onClick={() => { void changeStyle(suggestion.style); setSuggestion(undefined); }}>Apply this style</button>
        <button type="button" className="option-btn" onClick={() => setSuggestion(undefined)}>Keep mine</button>
      </div>}
      {styleError && <p className="dashboard-error" role="alert">{styleError}</p>}
    </section>
  );
  return <aside className="agent-dashboard" aria-label="Resume Builder dashboard"><button className="dashboard-close" onClick={onClose} aria-label="Close dashboard">×</button><h2>Resume Builder</h2><div className="dashboard-card"><span>Selected Resume</span><strong>{state.resumeTitle || "No resume selected"}</strong></div><div className="dashboard-card"><span>Workflow</span><strong>{state.step.replaceAll("_", " ")}</strong></div>{experienceLevel && <div className="dashboard-card"><span>Resume Plan</span><strong>{experienceLevel === "fresher" ? "Fresher" : "Experienced"} · {pagePlan}</strong></div>}{state.atsScore !== undefined && <div className="dashboard-card"><span>ATS Score</span><strong style={{ color: state.atsScore >= 80 ? "#10b981" : state.atsScore >= 60 ? "#f59e0b" : "#ef4444" }}>{state.atsScore}/100{state.draft?.targetRole ? ` · ${state.draft.targetRole}` : ""}</strong></div>}{state.resumeId && templates.length > 0 && <label className="dashboard-card"><span>Template</span><select value={templateChoice} disabled={savingTemplate || downloading} onChange={(event) => void chooseTemplate(event.target.value)}>{templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}</select></label>}{styleControls}{state.resumeId && <section className="resume-dashboard-preview"><b>Resume Preview</b>{previewUrl ? <iframe title="Resume PDF preview" src={previewUrl} /> : <p>{previewError || "Preparing your saved resume preview…"}</p>}</section>}{state.resumeId && <button className="option-btn" disabled={downloading} onClick={() => void download()}>{downloading ? "Preparing PDF…" : "Download PDF"}</button>}{downloadError && <p className="dashboard-error" role="alert">{downloadError}</p>}</aside>;
}
