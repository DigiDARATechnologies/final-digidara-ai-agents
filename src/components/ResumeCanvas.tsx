import { useEffect, useRef, useState } from "react";
import type { User } from "../types";
import type { ResumeCanvasState } from "../lib/resumeCanvasState";
import {
  analyzeResumeUpload,
  analyzeSavedResume,
  createImportDraft,
  createResume,
  exportResumePdf,
  generateImportedResume,
  getResume,
  listResumeTemplates,
  previewResumePdf,
  selectResumeTemplate,
  suggestResumeEdit,
  updateResume,
  type ResumeEditProposal,
  type ResumeTemplate,
} from "../lib/resumeBuilderApi";

interface ResumeCanvasProps {
  user: User;
  state: ResumeCanvasState;
  onStateChange: (state: ResumeCanvasState) => void;
}

type Doc = Record<string, unknown>;
type Score = { normalized_score?: number; breakdown?: Record<string, { label?: string; earned?: number; pointsEarned?: number; maximum?: number; maxPoints?: number }>; skills?: { matched_required?: string[]; missing_required?: string[] }; recommendations?: { priority?: string; problem?: string; fix?: string }[] };

function skillName(item: unknown): string {
  return typeof item === "string" ? item : String((item as { skill?: string })?.skill || "");
}

function asRecord(value: unknown): Doc {
  return (value && typeof value === "object" ? value : {}) as Doc;
}

/** Everything the score panel needs, read defensively -- the analyzer's shape
 * has evolved a few times, so every field is read defensively. */
function readScore(analysis: Doc): Score {
  const score = asRecord(analysis.score);
  const skills = asRecord(analysis.skills);
  const missing = [...(Array.isArray(skills.missing_required) ? skills.missing_required : []), ...(Array.isArray(skills.missing_preferred) ? skills.missing_preferred : [])]
    .map(skillName).filter(Boolean);
  const matched = [...(Array.isArray(skills.matched_required) ? skills.matched_required : []), ...(Array.isArray(skills.matched_preferred) ? skills.matched_preferred : [])]
    .map(skillName).filter(Boolean);
  return {
    normalized_score: Number(score.normalized_score) || 0,
    breakdown: (analysis.breakdown as Score["breakdown"]) || undefined,
    skills: { missing_required: missing, matched_required: matched },
    recommendations: Array.isArray(analysis.recommendations) ? (analysis.recommendations as Score["recommendations"]) : [],
  };
}

function scoreColor(value: number): string {
  return value >= 80 ? "#10b981" : value >= 60 ? "#f59e0b" : "#ef4444";
}

export default function ResumeCanvas({ user, state, onStateChange }: ResumeCanvasProps) {
  const [resumeId, setResumeId] = useState<number | undefined>(state.resumeId);
  const [document, setDocument] = useState<Doc | null>(null);
  const [score, setScore] = useState<Score | null>(null);
  const [scoring, setScoring] = useState(false);
  const [loadError, setLoadError] = useState("");

  // ---- Stage 1: start ----
  const [starting, setStarting] = useState<"upload" | "interview" | null>(null);
  const [startError, setStartError] = useState("");
  const [interview, setInterview] = useState({ role: "", level: "fresher" as "fresher" | "experienced", lastRole: "", skills: "", achievement: "" });
  const [pastedText, setPastedText] = useState("");

  // ---- Editable fields ----
  const saveTimer = useRef<number | undefined>(undefined);

  // ---- Copilot ----
  const [chatInput, setChatInput] = useState("");
  const [copilotBusy, setCopilotBusy] = useState(false);
  const [copilotError, setCopilotError] = useState("");
  const [proposal, setProposal] = useState<ResumeEditProposal | null>(null);

  // ---- Tailor ----
  const [jdText, setJdText] = useState("");

  // ---- Templates / export ----
  const [templates, setTemplates] = useState<ResumeTemplate[]>([]);
  const [templateChoice, setTemplateChoice] = useState("steady-form");
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewError, setPreviewError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  useEffect(() => { void listResumeTemplates().then(setTemplates).catch(() => setTemplates([])); }, []);

  // Reload the document (and its score) once we know which resume this chat is about --
  // covers both the initial mount-from-persisted-state and right after creation/import.
  useEffect(() => {
    if (!resumeId) return;
    let active = true;
    void getResume(user.id, resumeId)
      .then((resume) => {
        if (!active) return;
        setDocument(resume);
        setLoadError("");
        if (typeof resume.template_choice === "string" && resume.template_choice) setTemplateChoice(resume.template_choice);
        return refreshScore(resumeId);
      })
      .catch((error) => { if (active) setLoadError((error as Error).message || "Could not load this resume."); });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeId, user.id]);

  useEffect(() => {
    if (!document) return;
    let active = true;
    let url = "";
    void previewResumePdf(user.id, document, templateChoice)
      .then((blob) => { if (active) { url = URL.createObjectURL(blob); setPreviewUrl(url); setPreviewError(""); } })
      .catch((error) => { if (active) setPreviewError((error as Error).message || "Preview failed."); });
    return () => { active = false; if (url) URL.revokeObjectURL(url); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [document, templateChoice, user.id]);

  useEffect(() => {
    const nextScore = score?.normalized_score;
    onStateChange({
      step: !resumeId ? "empty" : (nextScore ?? 0) >= 70 ? "ready" : "editing",
      resumeId,
      resumeTitle: typeof document?.title === "string" ? document.title : undefined,
      atsScore: nextScore,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeId, document?.title, score?.normalized_score]);

  async function refreshScore(id: number) {
    setScoring(true);
    try {
      const analysis = await analyzeSavedResume(user.id, id);
      setScore(readScore(analysis as Doc));
    } catch {
      // Scoring is a nice-to-have on top of an already-saved resume; a transient
      // failure here should never block editing.
    } finally {
      setScoring(false);
    }
  }

  function updateField(patch: Doc) {
    setDocument((current) => (current ? { ...current, ...patch } : current));
    if (!resumeId) return;
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => {
      void updateResume(user.id, resumeId, patch).then(() => refreshScore(resumeId)).catch(() => {});
    }, 700);
  }

  // ---------------------------------------------------------------- stage 1 --

  async function startFromUpload(file: File) {
    setStarting("upload");
    setStartError("");
    try {
      const analysis = await analyzeResumeUpload(user.id, file);
      const draft = await createImportDraft(user.id, file.name, analysis.parsedResume, analysis.atsAnalysis ?? {}, "", "fresher");
      const id = Number(draft.id);
      try {
        const generated = await generateImportedResume(user.id, draft, String(draft.target_role || ""));
        if (generated?.resume) await updateResume(user.id, id, generated.resume);
      } catch {
        // Keep the clean imported draft if AI wording generation has a transient failure.
      }
      setResumeId(id);
    } catch (error) {
      setStartError((error as Error).message || "Could not read that file.");
    } finally {
      setStarting(null);
    }
  }

  async function startFromPastedText() {
    const text = pastedText.trim();
    if (!text) return;
    // Same extraction pipeline as a file upload -- LinkedIn gives no API access to
    // auto-fetch a profile, but its "About"/experience text pastes in just as well
    // as a resume's, and the parser doesn't care which one it came from.
    await startFromUpload(new File([text], "pasted-notes.txt", { type: "text/plain" }));
  }

  async function startFromInterview() {
    setStarting("interview");
    setStartError("");
    try {
      const skills = interview.skills.split(",").map((value) => value.trim()).filter(Boolean).map((skill_name) => ({ skill_name }));
      const created = await createResume(user.id, {
        title: interview.role ? `${interview.role} Resume` : "My Resume",
        target_role: interview.role,
        experience_level: interview.level,
        summary: "",
        personal_info: { name: user.name, email: user.email, phone: user.mobile },
        skills,
        experience: interview.lastRole ? [{ company: interview.lastRole, role: interview.role || "Team Member", raw_input: interview.lastRole }] : [],
        education: [],
        projects: [],
        achievements: interview.achievement ? [{ title: interview.achievement }] : [],
      });
      setResumeId(Number(created.id));
    } catch (error) {
      setStartError((error as Error).message || "Could not start your resume.");
    } finally {
      setStarting(null);
    }
  }

  // ------------------------------------------------------------- copilot --

  async function sendCopilot(instruction: string) {
    const text = instruction.trim();
    if (!text || !document || !resumeId) return;
    setCopilotBusy(true);
    setCopilotError("");
    try {
      const result = await suggestResumeEdit(user.id, document, text);
      setProposal(result);
      setChatInput("");
    } catch (error) {
      setCopilotError((error as Error).message || "I could not prepare that edit.");
    } finally {
      setCopilotBusy(false);
    }
  }

  async function applyProposal() {
    if (!proposal || !resumeId) return;
    const saved = await updateResume(user.id, resumeId, proposal.resume);
    setDocument(saved);
    setProposal(null);
    await refreshScore(resumeId);
  }

  // ---------------------------------------------------------- template/export --

  async function chooseTemplate(value: string) {
    if (!resumeId) return;
    setTemplateChoice(value);
    await selectResumeTemplate(user.id, resumeId, value).catch(() => {});
  }

  async function download() {
    if (!resumeId || downloading) return;
    setDownloading(true);
    setDownloadError("");
    try {
      const { blob, filename } = await exportResumePdf(user.id, resumeId, templateChoice);
      if (!blob.size) throw new Error("The generated PDF was empty. Please try again.");
      const url = URL.createObjectURL(blob);
      const link = window.document.createElement("a");
      link.href = url; link.download = filename; link.style.display = "none";
      window.document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
    } catch (error) {
      setDownloadError((error as Error).message || "PDF download failed.");
    } finally {
      setDownloading(false);
    }
  }

  // ------------------------------------------------------------------ render --

  if (!resumeId) {
    return (
      <div className="resume-canvas resume-canvas-start">
        <h2>Let's build your resume</h2>
        <p className="muted">Start with whatever you already have. You'll see a full draft in under a minute.</p>
        <div className="resume-start-options">
          <label className="resume-start-card">
            <span>Upload a resume</span>
            <strong>PDF, DOCX, DOC, or TXT</strong>
            <input type="file" accept=".pdf,.doc,.docx,.txt" style={{ display: "none" }}
              onChange={(event) => { const file = event.target.files?.[0]; if (file) void startFromUpload(file); }} />
          </label>
          <div className="resume-start-card">
            <span>Paste your LinkedIn or notes</span>
            <strong>LinkedIn profile text, or any rough notes</strong>
            <div className="resume-interview-form">
              <textarea rows={4} placeholder="Paste your LinkedIn 'About' and experience text, or just rough notes about your background…"
                value={pastedText} onChange={(event) => setPastedText(event.target.value)} />
              <button type="button" className="btn btn-primary" disabled={starting === "upload" || !pastedText.trim()} onClick={() => void startFromPastedText()}>
                {starting === "upload" ? "Reading…" : "Use this text"}
              </button>
            </div>
          </div>
          <div className="resume-start-card">
            <span>Start fresh</span>
            <strong>A 5-question quick interview</strong>
            <div className="resume-interview-form">
              <input placeholder="Target role (e.g. Data Analyst)" value={interview.role} onChange={(event) => setInterview({ ...interview, role: event.target.value })} />
              <select value={interview.level} onChange={(event) => setInterview({ ...interview, level: event.target.value as "fresher" | "experienced" })}>
                <option value="fresher">Fresher / student</option>
                <option value="experienced">Experienced professional</option>
              </select>
              <input placeholder="Last job or college" value={interview.lastRole} onChange={(event) => setInterview({ ...interview, lastRole: event.target.value })} />
              <input placeholder="Top skills, comma separated" value={interview.skills} onChange={(event) => setInterview({ ...interview, skills: event.target.value })} />
              <input placeholder="One achievement you're proud of" value={interview.achievement} onChange={(event) => setInterview({ ...interview, achievement: event.target.value })} />
              <button type="button" className="btn btn-primary" disabled={starting === "interview"} onClick={() => void startFromInterview()}>
                {starting === "interview" ? "Preparing your draft…" : "Create my first draft"}
              </button>
            </div>
          </div>
        </div>
        {starting === "upload" && <p className="muted">Reading your resume…</p>}
        {startError && <p className="form-error" role="alert">{startError}</p>}
      </div>
    );
  }

  const title = typeof document?.title === "string" ? document.title : "";
  const targetRole = typeof document?.target_role === "string" ? document.target_role : "";
  const summary = typeof document?.summary === "string" ? document.summary : "";
  const skills = Array.isArray(document?.skills) ? (document!.skills as Doc[]).map((item) => String(item.skill_name || "")) : [];
  const experience = Array.isArray(document?.experience) ? (document!.experience as Doc[]) : [];
  const education = Array.isArray(document?.education) ? (document!.education as Doc[]) : [];
  const projects = Array.isArray(document?.projects) ? (document!.projects as Doc[]) : [];

  return (
    <div className="resume-canvas">
      <div className="resume-canvas-editor">
        {loadError && <p className="form-error" role="alert">{loadError}</p>}
        <label className="field"><span>Resume title</span><input value={title} onChange={(event) => updateField({ title: event.target.value })} /></label>
        <label className="field"><span>Target role</span><input value={targetRole} onChange={(event) => updateField({ target_role: event.target.value })} /></label>
        <label className="field"><span>Professional summary</span>
          <textarea rows={3} value={summary} placeholder="Add a summary here" onChange={(event) => updateField({ summary: event.target.value })} />
        </label>
        <label className="field"><span>Skills</span>
          <input value={skills.join(", ")} placeholder="Add your skills, comma separated"
            onChange={(event) => updateField({ skills: event.target.value.split(",").map((value) => value.trim()).filter(Boolean).map((skill_name) => ({ skill_name })) })} />
        </label>

        <section className="resume-section-list">
          <h4>Experience{!experience.length && <span className="muted"> — add a role here</span>}</h4>
          {experience.map((item, index) => (
            <div className="resume-entry-card" key={index}>
              <b>{String(item.role || "Role")} · {String(item.company || "Company")}</b>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setChatInput(`Improve the bullets for my role at ${item.company}`)}>Edit with AI</button>
            </div>
          ))}
          <h4>Projects{!projects.length && <span className="muted"> — add a project here</span>}</h4>
          {projects.map((item, index) => (
            <div className="resume-entry-card" key={index}><b>{String(item.title || "Project")}</b>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setChatInput(`Improve the description for my "${item.title}" project`)}>Edit with AI</button>
            </div>
          ))}
          <h4>Education{!education.length && <span className="muted"> — add your education here</span>}</h4>
          {education.map((item, index) => <div className="resume-entry-card" key={index}><b>{String(item.school || "School")}</b></div>)}
        </section>

        <section className="resume-preview-pane">
          <div className="resume-toolbar">
            {templates.length > 0 && (
              <select value={templateChoice} onChange={(event) => void chooseTemplate(event.target.value)}>
                {templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
              </select>
            )}
            <button type="button" className="btn btn-primary btn-sm" disabled={downloading} onClick={() => void download()}>
              {downloading ? "Preparing PDF…" : "Download PDF"}
            </button>
          </div>
          {previewUrl ? <iframe title="Resume preview" src={previewUrl} className="resume-preview-frame" /> : <p className="muted">{previewError || "Preparing your resume preview…"}</p>}
          {downloadError && <p className="form-error" role="alert">{downloadError}</p>}
        </section>
      </div>

      <div className="resume-canvas-copilot">
        <div className="resume-score-panel">
          <div className="resume-score-value" style={{ color: scoreColor(score?.normalized_score ?? 0) }}>
            {scoring ? "…" : `${score?.normalized_score ?? 0}/100`}
          </div>
          <span className="muted">ATS score</span>
          <div className="resume-chips">
            {(score?.skills?.missing_required ?? []).slice(0, 4).map((name) => (
              <button type="button" className="btn btn-outline btn-sm" key={name} onClick={() => void sendCopilot(`Add "${name}" naturally to my skills or experience where it genuinely fits.`)}>
                Missing: {name} → Fix with AI
              </button>
            ))}
            {!summary && (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => void sendCopilot("Write a strong professional summary for my target role.")}>No summary → Fix with AI</button>
            )}
          </div>
        </div>

        <div className="resume-copilot-chat">
          <h4>Copilot</h4>
          <p className="muted">Ask for changes -- "make my bullets more impact-driven", "add my internship at TCS".</p>
          <textarea rows={2} value={chatInput} placeholder="Tell me what to change…" onChange={(event) => setChatInput(event.target.value)} />
          <button type="button" className="btn btn-primary" disabled={copilotBusy || !chatInput.trim()} onClick={() => void sendCopilot(chatInput)}>
            {copilotBusy ? "Thinking…" : "Send"}
          </button>
          {copilotError && <p className="form-error" role="alert">{copilotError}</p>}

          {proposal && (
            <div className="resume-proposal">
              <b>Proposed changes</b>
              <ul>{proposal.changes.map((change, index) => <li key={index}>{change}</li>)}</ul>
              {proposal.warnings.length > 0 && <p className="muted">{proposal.warnings.join(" ")}</p>}
              <div className="resume-proposal-actions">
                <button type="button" className="btn btn-primary btn-sm" onClick={() => void applyProposal()}>Apply</button>
                <button type="button" className="btn btn-outline btn-sm" onClick={() => setChatInput((current) => current || "Try a different approach: ")}>Revise</button>
                <button type="button" className="btn btn-outline btn-sm" onClick={() => setProposal(null)}>Cancel</button>
              </div>
            </div>
          )}
        </div>

        <div className="resume-tailor">
          <h4>Tailor to a job</h4>
          <textarea rows={3} value={jdText} placeholder="Paste a job description…" onChange={(event) => setJdText(event.target.value)} />
          <button type="button" className="btn btn-outline" disabled={copilotBusy || !jdText.trim()}
            onClick={() => void sendCopilot(`Tailor my resume for this job description, emphasizing relevant skills and matching its keywords naturally, without fabricating experience:\n\n${jdText}`)}>
            Tailor my resume
          </button>
        </div>
      </div>
    </div>
  );
}
