import type { User } from "../types";
import type { ResumeBuilderFlowState } from "../lib/resumeBuilderFlow";
import { exportResumePdf } from "../lib/resumeBuilderApi";

export default function ResumeBuilderDashboard({ user, state, onClose }: { user: User; state: ResumeBuilderFlowState; onClose: () => void }) {
  const experienceLevel = state.draft?.experienceLevel;
  const pagePlan = experienceLevel === "experienced" ? "Up to 2 pages" : experienceLevel === "fresher" ? "1 page" : undefined;
  async function download() { if (!state.resumeId) return; const { blob, filename } = await exportResumePdf(user.id, state.resumeId, state.templateChoice); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = filename; link.click(); URL.revokeObjectURL(link.href); }
  return <aside className="agent-dashboard" aria-label="Resume Builder dashboard"><button className="dashboard-close" onClick={onClose} aria-label="Close dashboard">×</button><h2>Resume Builder</h2><div className="dashboard-card"><span>Selected resume</span><strong>{state.resumeTitle || "No resume selected"}</strong></div><div className="dashboard-card"><span>Workflow</span><strong>{state.step.replaceAll("_", " ")}</strong></div>{experienceLevel && <div className="dashboard-card"><span>Resume plan</span><strong>{experienceLevel === "fresher" ? "Fresher" : "Experienced"} · {pagePlan}</strong></div>}{state.atsScore !== undefined && <div className="dashboard-card"><span>ATS score</span><strong>{state.atsScore}/100</strong></div>}{state.resumeId && <button className="option-btn" onClick={() => void download()}>Download PDF</button>}</aside>;
}
