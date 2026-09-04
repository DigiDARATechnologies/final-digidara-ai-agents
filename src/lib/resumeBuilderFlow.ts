import type { ChatOption, User } from "../types";
import { analyzeResumeUpload, createImportDraft, createResume, ensureResumeProfile, type ResumeCreateInput } from "./resumeBuilderApi";

export type ResumeBuilderStep = "choose_workflow" | "awaiting_experience_level" | "awaiting_title" | "awaiting_name" | "awaiting_email" | "awaiting_phone" | "awaiting_location" | "awaiting_role" | "awaiting_summary" | "awaiting_skills" | "awaiting_experience" | "awaiting_education" | "awaiting_project" | "confirming" | "awaiting_upload_role" | "awaiting_upload_job_description" | "awaiting_upload" | "reviewing" | "completed" | "error";
interface ResumeDraft {
  title?: string; name?: string; email?: string; phone?: string; location?: string; targetRole?: string; jobDescription?: string; experienceLevel?: "fresher" | "experienced"; summary?: string;
  skills?: string[]; experience?: ResumeCreateInput["experience"]; education?: ResumeCreateInput["education"]; projects?: ResumeCreateInput["projects"];
}
export interface ResumeBuilderFlowState { step: ResumeBuilderStep; draft?: ResumeDraft; resumeId?: number; resumeTitle?: string; atsScore?: number; templateChoice?: string; error?: string; }
export interface ResumeBuilderMessage { text: string; options?: ChatOption[]; }
export interface ResumeBuilderFlowResult { state: ResumeBuilderFlowState; messages: ResumeBuilderMessage[]; }
export const createInitialResumeBuilderState = (): ResumeBuilderFlowState => ({ step: "choose_workflow" });
const choices: ChatOption[] = [{ label: "Create a resume", value: "new", description: "Start with a blank, editable resume." }, { label: "Upload an existing resume", value: "upload", description: "Import PDF, DOC, DOCX, or TXT for review." }];
const skipOption: ChatOption[] = [{ label: "Skip this section", value: "skip", description: "You can add it later from your resume editor." }];
const restartOption: ChatOption[] = [{ label: "Start over", value: "restart", description: "Discard this draft and begin again." }];

function clean(value: string) { return value.trim(); }
function isSkip(value: string) { return clean(value).toLowerCase() === "skip"; }
function updateDraft(state: ResumeBuilderFlowState, draft: Partial<ResumeDraft>, step: ResumeBuilderStep): ResumeBuilderFlowState {
  return { ...state, step, draft: { ...state.draft, ...draft } };
}
function splitFields(value: string, expected: number) {
  const fields = value.split("|").map(clean);
  return fields.length >= expected && fields.slice(0, expected).every(Boolean) ? fields : null;
}
function reviewMessage(draft: ResumeDraft): ResumeBuilderMessage {
  const pagePlan = draft.experienceLevel === "fresher" ? "One-page ATS resume" : "Up to two-page ATS resume";
  return { text: `Please review your details:\n• ${draft.name} — ${draft.email}\n• Target role: ${draft.targetRole}\n• Career level: ${draft.experienceLevel === "fresher" ? "Fresher" : "Experienced"} (${pagePlan})\n• Skills: ${(draft.skills || []).join(", ") || "Not added"}\n• Experience: ${draft.experience?.length || 0} entry\n• Education: ${draft.education?.length || 0} entry\n• Projects: ${draft.projects?.length || 0} entry\n\nEverything looks right?`, options: [{ label: "Create my resume", value: "create_now", description: "Create your editable resume with these details." }, ...restartOption] };
}

async function createFromDraft(state: ResumeBuilderFlowState, user: User): Promise<ResumeBuilderFlowResult> {
  const draft = state.draft;
  if (!draft?.title || !draft.name || !draft.email || !draft.targetRole || !draft.experienceLevel || !draft.summary) {
    return { state: { ...state, step: "error", error: "Your required resume details are incomplete." }, messages: [{ text: "Your required details are incomplete. Please choose Start over and complete the required fields.", options: restartOption }] };
  }
  try {
    const resume = await createResume(user.id, {
      title: draft.title,
      target_role: draft.targetRole,
      experience_level: draft.experienceLevel,
      summary: draft.summary,
      personal_info: { name: draft.name, email: draft.email, phone: draft.phone, location: draft.location },
      skills: (draft.skills || []).map((skill_name) => ({ skill_name })),
      experience: draft.experience || [],
      education: draft.education || [],
      projects: draft.projects || [],
    });
    const id = Number(resume.id);
    return { state: { ...state, step: "reviewing", resumeId: id, resumeTitle: String(resume.title || draft.title) }, messages: [{ text: "Your resume has been created with all the details you provided. Open Dashboard to review it, download the PDF, or continue improving it." }] };
  } catch (error) {
    return { state: { ...state, step: "confirming", error: (error as Error).message }, messages: [{ text: `I couldn’t create the resume: ${(error as Error).message}. Your details are still saved in this chat.`, options: [{ label: "Try creating again", value: "create_now" }, ...restartOption] }] };
  }
}

export async function openResumeBuilderChat(user: User): Promise<ResumeBuilderFlowResult> {
  const state = createInitialResumeBuilderState();
  try { await ensureResumeProfile(user.id, user.name, user.email); return { state, messages: [{ text: `Hi ${user.name.split(" ")[0]}! Would you like to create a new resume or upload one to improve?`, options: choices }] }; }
  catch (error) { return { state: { ...state, step: "error", error: (error as Error).message }, messages: [{ text: `I could not initialize Resume Builder: ${(error as Error).message}`, options: [{ label: "Try again", value: "retry" }] }] }; }
}

export async function handleResumeBuilderText(state: ResumeBuilderFlowState, user: User, value: string): Promise<ResumeBuilderFlowResult> {
  if (value === "retry" || value === "restart") return openResumeBuilderChat(user);
  if (state.step === "choose_workflow") {
    if (value === "new") return { state: { ...state, step: "awaiting_experience_level", draft: {} }, messages: [{ text: "Before we begin, which best describes you? This sets the right resume length and section priorities.", options: [{ label: "Fresher / student", value: "fresher", description: "A concise, one-page resume focused on education, projects, skills, and internships." }, { label: "Experienced professional", value: "experienced", description: "A resume designed for up to two pages, with room for career impact and achievements." }] }] };
    if (value === "upload") return { state: { ...state, step: "awaiting_upload_role", draft: {} }, messages: [{ text: "What role are you targeting with this resume? For example: Data Analyst or Python Developer." }] };
  }
  if (state.step === "awaiting_experience_level") {
    if (value !== "fresher" && value !== "experienced") return { state, messages: [{ text: "Please choose Fresher / student or Experienced professional from the options." }] };
    if (state.draft?.targetRole) {
      return { state: updateDraft(state, { experienceLevel: value }, "awaiting_upload"), messages: [{ text: `Attach your PDF, DOC, DOCX, or TXT resume. I’ll analyze it against the ${state.draft.targetRole} role and create an editable ${value === "fresher" ? "one-page" : "up-to-two-page"} ATS version.` }] };
    }
    return { state: updateDraft(state, { experienceLevel: value }, "awaiting_title"), messages: [{ text: `Great. We’ll create a ${value === "fresher" ? "focused one-page" : "detailed, up-to-two-page"} ATS resume. What should we call it? For example: ‘Data Analyst Resume’.` }] };
  }
  if (state.step === "awaiting_title") {
    if (clean(value).length < 3) return { state, messages: [{ text: "Please use a title with at least 3 characters, such as ‘Frontend Developer Resume’." }] };
    return { state: updateDraft(state, { title: clean(value) }, "awaiting_name"), messages: [{ text: "What is your full name?" }] };
  }
  if (state.step === "awaiting_name") {
    if (clean(value).length < 2) return { state, messages: [{ text: "Please enter your full name." }] };
    return { state: updateDraft(state, { name: clean(value) }, "awaiting_email"), messages: [{ text: "What is your professional email address?" }] };
  }
  if (state.step === "awaiting_email") {
    const email = clean(value).toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return { state, messages: [{ text: "Please enter a valid email address, for example name@example.com." }] };
    return { state: updateDraft(state, { email }, "awaiting_phone"), messages: [{ text: "What is your phone number? Type Skip if you prefer not to include one.", options: skipOption }] };
  }
  if (state.step === "awaiting_phone") return { state: updateDraft(state, { phone: isSkip(value) ? "" : clean(value) }, "awaiting_location"), messages: [{ text: "What city and country should appear on your resume? Type Skip to omit it.", options: skipOption }] };
  if (state.step === "awaiting_location") return { state: updateDraft(state, { location: isSkip(value) ? "" : clean(value) }, "awaiting_role"), messages: [{ text: "What role are you targeting? For example: Data Analyst or Frontend Developer." }] };
  if (state.step === "awaiting_role") {
    if (clean(value).length < 2) return { state, messages: [{ text: "Please enter the role you are targeting." }] };
    return { state: updateDraft(state, { targetRole: clean(value) }, "awaiting_summary"), messages: [{ text: "Write a short professional summary (2–4 sentences). Focus on your experience, strengths, and the value you bring." }] };
  }
  if (state.step === "awaiting_summary") {
    if (clean(value).length < 30) return { state, messages: [{ text: "Please add a little more detail—at least 30 characters makes your summary useful to recruiters." }] };
    return { state: updateDraft(state, { summary: clean(value) }, "awaiting_skills"), messages: [{ text: "List your key skills, separated by commas. For example: Python, SQL, Power BI, Excel." }] };
  }
  if (state.step === "awaiting_skills") {
    const skills = clean(value).split(",").map(clean).filter(Boolean);
    if (!skills.length) return { state, messages: [{ text: "Please add at least one skill, separated by commas." }] };
    const experienceHint = state.draft?.experienceLevel === "fresher" ? "Add an internship, volunteer role, or relevant practical experience" : "Add your most recent experience";
    return { state: updateDraft(state, { skills: [...new Set(skills)].slice(0, 20) }, "awaiting_experience"), messages: [{ text: `${experienceHint} in this format:\nCompany | Role | Start date | End date or Present | Key achievements/responsibilities\n\nExample: Acme | Data Analyst | Jan 2024 | Present | Built Power BI dashboards that reduced reporting time by 30%.\n\nType Skip if you do not want to add experience.`, options: skipOption }] };
  }
  if (state.step === "awaiting_experience") {
    if (isSkip(value)) return { state: updateDraft(state, { experience: [] }, "awaiting_education"), messages: [{ text: "Add your highest education in this format:\nSchool | Degree | Field of study | Start year | End year\n\nExample: Anna University | B.Tech | Computer Science | 2020 | 2024\n\nType Skip to omit it.", options: skipOption }] };
    const fields = splitFields(value, 5);
    if (!fields) return { state, messages: [{ text: "Please use: Company | Role | Start date | End date or Present | Key achievements." }] };
    const [company, role, start_date, end_date, raw_input] = fields;
    return { state: updateDraft(state, { experience: [{ company, role, start_date, end_date, is_current: /^(present|current|now)$/i.test(end_date), raw_input }] }, "awaiting_education"), messages: [{ text: "Add your highest education in this format:\nSchool | Degree | Field of study | Start year | End year\n\nExample: Anna University | B.Tech | Computer Science | 2020 | 2024\n\nType Skip to omit it.", options: skipOption }] };
  }
  if (state.step === "awaiting_education") {
    if (isSkip(value)) return { state: updateDraft(state, { education: [] }, "awaiting_project"), messages: [{ text: "Add one relevant project in this format:\nProject title | What you built and its outcome\n\nType Skip if you do not want to add a project.", options: skipOption }] };
    const fields = splitFields(value, 5);
    if (!fields) return { state, messages: [{ text: "Please use: School | Degree | Field of study | Start year | End year." }] };
    const [school, degree, field, start_date, end_date] = fields;
    return { state: updateDraft(state, { education: [{ school, degree, field, start_date, end_date }] }, "awaiting_project"), messages: [{ text: "Add one relevant project in this format:\nProject title | What you built and its outcome\n\nType Skip if you do not want to add a project.", options: skipOption }] };
  }
  if (state.step === "awaiting_project") {
    const projectFields = isSkip(value) ? null : splitFields(value, 2);
    if (!isSkip(value) && !projectFields) return { state, messages: [{ text: "Please use: Project title | What you built and its outcome. Or choose Skip." , options: skipOption }] };
    const next = updateDraft(state, { projects: projectFields ? [{ title: projectFields[0], description: projectFields.slice(1).join(" | ") }] : [] }, "confirming");
    return { state: next, messages: [reviewMessage(next.draft || {})] };
  }
  if (state.step === "awaiting_upload_role") {
    if (clean(value).length < 2) return { state, messages: [{ text: "Please enter the role you are targeting." }] };
    return { state: updateDraft(state, { targetRole: clean(value) }, "awaiting_upload_job_description"), messages: [{ text: "Paste the job description for that role, if you have it. This lets the ATS analysis compare your resume to the role. Type Skip if you do not have one yet.", options: skipOption }] };
  }
  if (state.step === "awaiting_upload_job_description") {
    return { state: updateDraft(state, { jobDescription: isSkip(value) ? "" : clean(value) }, "awaiting_experience_level"), messages: [{ text: "Finally, choose your career level so I can apply the right one-page or two-page structure.", options: [{ label: "Fresher / student", value: "fresher", description: "One-page structure prioritizing skills, education, and projects." }, { label: "Experienced professional", value: "experienced", description: "Up-to-two-page structure prioritizing measurable work impact." }] }] };
  }
  if (state.step === "confirming" && value === "create_now") return createFromDraft(state, user);
  return { state, messages: [{ text: "Choose Create a resume or Upload an existing resume to continue.", options: choices }] };
}

export async function importResumeBuilderFile(state: ResumeBuilderFlowState, user: User, file: File): Promise<ResumeBuilderFlowResult> {
  try {
    const targetRole = state.draft?.targetRole || "";
    const experienceLevel = state.draft?.experienceLevel || "fresher";
    const analysis = await analyzeResumeUpload(user.id, file, targetRole, state.draft?.jobDescription || "");
    const atsAnalysis = analysis.atsAnalysis as { normalizedScore?: number; score?: { normalized_score?: number } } | undefined;
    const resume = await createImportDraft(user.id, file.name, analysis.parsedResume, atsAnalysis ?? {}, targetRole, experienceLevel);
    const score = Number(atsAnalysis?.normalizedScore ?? atsAnalysis?.score?.normalized_score);
    const id = Number(resume.id);
    return { state: { ...state, step: "reviewing", resumeId: id, resumeTitle: String(resume.title || file.name), atsScore: Number.isFinite(score) ? score : undefined, draft: { ...state.draft, experienceLevel } }, messages: [{ text: `Imported ${file.name} into an editable draft${Number.isFinite(score) ? ` (ATS score: ${score}/100)` : ""}. It was analyzed for ${targetRole || "your selected role"}. Open Dashboard to review it.` }] };
  }
  catch (error) { return { state: { ...state, step: "error", error: (error as Error).message }, messages: [{ text: `I couldn’t analyze that file: ${(error as Error).message}`, options: [{ label: "Try again", value: "retry" }] }] }; }
}
