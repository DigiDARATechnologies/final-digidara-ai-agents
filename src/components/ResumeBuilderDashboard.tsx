import { useEffect, useState } from "react";
import type { User } from "../types";
import type { ResumeBuilderFlowState } from "../lib/resumeBuilderFlow";
import { exportResumePdf, getResume, listResumeTemplates, previewResumePdf, selectResumeTemplate, type ResumeTemplate } from "../lib/resumeBuilderApi";

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
  useEffect(() => { void listResumeTemplates().then(setTemplates).catch(() => setTemplates([])); }, []);
  useEffect(() => {
    if (!state.resumeId) return;
    void getResume(user.id, state.resumeId)
      .then((resume) => {
        setSavedResume(resume);
        if (typeof resume.template_choice === "string" && resume.template_choice) setTemplateChoice(resume.template_choice);
      })
      .catch(() => { setSavedResume(undefined); });
  }, [state.resumeId, user.id]);
  useEffect(() => {
    if (!savedResume) return;
    let active = true;
    let url = "";
    setPreviewUrl("");
    setPreviewError("");
    void previewResumePdf(user.id, savedResume, templateChoice)
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
  }, [savedResume, templateChoice, user.id]);
  async function chooseTemplate(value: string) {
    if (!state.resumeId) return;
    setSavingTemplate(true);
    try {
      await selectResumeTemplate(user.id, state.resumeId, value);
      setTemplateChoice(value);
      setSavedResume((current) => current ? { ...current, template_choice: value } : current);
    } finally { setSavingTemplate(false); }
  }
  async function download() {
    if (!state.resumeId || downloading) return;
    setDownloading(true);
    setDownloadError("");
    try {
      const { blob, filename } = await exportResumePdf(user.id, state.resumeId, templateChoice);
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
  return <aside className="agent-dashboard" aria-label="Resume Builder dashboard"><button className="dashboard-close" onClick={onClose} aria-label="Close dashboard">×</button><h2>Resume Builder</h2><div className="dashboard-card"><span>Selected resume</span><strong>{state.resumeTitle || "No resume selected"}</strong></div><div className="dashboard-card"><span>Workflow</span><strong>{state.step.replaceAll("_", " ")}</strong></div>{experienceLevel && <div className="dashboard-card"><span>Resume plan</span><strong>{experienceLevel === "fresher" ? "Fresher" : "Experienced"} · {pagePlan}</strong></div>}{state.atsScore !== undefined && <div className="dashboard-card"><span>ATS score</span><strong style={{ color: state.atsScore >= 80 ? "#10b981" : state.atsScore >= 60 ? "#f59e0b" : "#ef4444" }}>{state.atsScore}/100{state.draft?.targetRole ? ` · ${state.draft.targetRole}` : ""}</strong></div>}{state.resumeId && templates.length > 0 && <label className="dashboard-card"><span>Template</span><select value={templateChoice} disabled={savingTemplate || downloading} onChange={(event) => void chooseTemplate(event.target.value)}>{templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}</select></label>}{state.resumeId && <section className="resume-dashboard-preview"><b>Resume preview</b>{previewUrl ? <iframe title="Resume PDF preview" src={previewUrl} /> : <p>{previewError || "Preparing your saved resume preview…"}</p>}</section>}{state.resumeId && <button className="option-btn" disabled={downloading} onClick={() => void download()}>{downloading ? "Preparing PDF…" : "Download PDF"}</button>}{downloadError && <p className="dashboard-error" role="alert">{downloadError}</p>}</aside>;
}
