import type { ChatOption, User } from "../types";
import {
  analyzeResumeUpload,
  createImportDraft,
  createResume,
  ensureResumeProfile,
  generateImportedResume,
  analyzeSavedResume,
  getResume,
  listResumeTemplates,
  selectResumeTemplate,
  suggestResumeEdit,
  updateResume,
  type ResumeEditProposal,
  type ResumeCreateInput,
} from "./resumeBuilderApi";

export type ResumeBuilderStep = "choose_workflow" | "awaiting_experience_level" | "awaiting_title" | "awaiting_name" | "awaiting_email" | "awaiting_phone" | "awaiting_location" | "awaiting_role" | "awaiting_summary" | "awaiting_skills" | "awaiting_experience" | "awaiting_experience_more" | "awaiting_education" | "awaiting_education_more" | "awaiting_project" | "awaiting_project_more" | "awaiting_linkedin" | "awaiting_github" | "awaiting_portfolio" | "awaiting_certifications" | "awaiting_certifications_more" | "awaiting_achievements" | "awaiting_achievements_more" | "confirming" | "awaiting_enrichment_choice" | "awaiting_upload_role" | "awaiting_upload_job_description" | "awaiting_upload" | "awaiting_import_linkedin" | "awaiting_import_github" | "awaiting_import_portfolio" | "reviewing" | "awaiting_edit_instruction" | "awaiting_edit_confirmation" | "awaiting_template" | "completed" | "error";
interface ResumeDraft {
  title?: string; name?: string; email?: string; phone?: string; location?: string; targetRole?: string; jobDescription?: string; experienceLevel?: "fresher" | "experienced"; summary?: string;
  skills?: string[]; experience?: ResumeCreateInput["experience"]; education?: ResumeCreateInput["education"]; projects?: ResumeCreateInput["projects"]; certifications?: NonNullable<ResumeCreateInput["certifications"]>; achievements?: NonNullable<ResumeCreateInput["achievements"]>; links?: string[];
  skipEducation?: boolean;
}
export interface ResumeBuilderFlowState { step: ResumeBuilderStep; draft?: ResumeDraft; resumeId?: number; resumeTitle?: string; atsScore?: number; templateChoice?: string; pendingField?: "education.ug"; pendingEdit?: ResumeEditProposal; pendingUploadFile?: File; error?: string; }
export interface ResumeBuilderMessage { text: string; options?: ChatOption[]; }
export interface ResumeBuilderFlowResult { state: ResumeBuilderFlowState; messages: ResumeBuilderMessage[]; }
export const createInitialResumeBuilderState = (): ResumeBuilderFlowState => ({ step: "choose_workflow" });
const choices: ChatOption[] = [{ label: "Create a resume", value: "new", description: "Start with a blank, editable resume." }, { label: "Upload an existing resume", value: "upload", description: "Import PDF, DOC, DOCX, or TXT for review." }];
const skipOption: ChatOption[] = [{ label: "Skip this section", value: "skip", description: "You can add it later from your resume editor." }];
const restartOption: ChatOption[] = [{ label: "Start over", value: "restart", description: "Discard this draft and begin again." }];
const editOptions: ChatOption[] = [
  { label: "Edit with AI", value: "edit_resume", description: "Describe the change you want; nothing is saved until you approve it." },
];
const reviewOptions: ChatOption[] = [
  ...editOptions,
  { label: "Generate final wording", value: "generate_resume", description: "Create grounded, target-role-specific resume wording from your verified details." },
];
const editConfirmationOptions: ChatOption[] = [
  { label: "Apply changes", value: "apply_edit", description: "Save this reviewed proposal to your resume." },
  { label: "Revise request", value: "revise_edit", description: "Keep your resume unchanged and send a different instruction." },
  { label: "Cancel", value: "cancel_edit", description: "Discard this proposal without changing your resume." },
];

function clean(value: string) { return value.trim(); }
function isSkip(value: string) { return clean(value).toLowerCase() === "skip"; }
function hasUndergraduateEducation(education: ResumeCreateInput["education"] | undefined) {
  return (education || []).some((item) => {
    const level = String(item.level || "").toUpperCase();
    const degree = String(item.degree || "");
    return level === "UG" || /\b(bca|b\.?sc|b\.?tech|b\.?e|bba|b\.?a|bachelor)\b/i.test(degree);
  });
}
function updateDraft(state: ResumeBuilderFlowState, draft: Partial<ResumeDraft>, step: ResumeBuilderStep): ResumeBuilderFlowState {
  return { ...state, step, draft: { ...state.draft, ...draft } };
}
function splitFields(value: string, expected: number) {
  const fields = value.split("|").map(clean);
  return fields.length >= expected && fields.slice(0, expected).every(Boolean) ? fields : null;
}
function educationLevel(degree: string, explicit = "") {
  if (explicit) return explicit.toUpperCase();
  if (/\b(mca|mba|m\.?sc|m\.?tech|master)/i.test(degree)) return "PG";
  if (/\b(bca|b\.?sc|b\.?tech|b\.?e|bba|b\.?a|bachelor)/i.test(degree)) return "UG";
  if (/diploma/i.test(degree)) return "Diploma";
  if (/ph\.?d|doctor/i.test(degree)) return "Doctorate";
  return "";
}
/** Parse concise, user-supplied education without supplying any missing fact. */
export function parseEducationInput(value: string): ResumeCreateInput["education"] | { error: string } {
  const entries = clean(value).split(/\s*;\s*/).filter(Boolean);
  const parsed: ResumeCreateInput["education"] = [];
  for (const raw of entries) {
    const label = raw.match(/^\s*(UG|PG|Diploma|Doctorate)\s*:\s*/i)?.[1] || "";
    const text = raw.replace(/^\s*(UG|PG|Diploma|Doctorate)\s*:\s*/i, "");
    // Accept natural punctuation and either "college | degree" or
    // "degree | college". Candidate wording is retained verbatim.
    const values = text.split(/\s*(?:\||,|\n|\s+-\s+)\s*/).map(clean).filter(Boolean);
    const degreeIndex = values.findIndex((item) => /\b(bca|b\.?sc|b\.?tech|b\.?e|bba|b\.?a|mca|m\.?sc|m\.?tech|mba|m\.?a|bachelor|master|diploma|ph\.?d)\b/i.test(item));
    const degree = degreeIndex >= 0 ? values[degreeIndex] : "";
    const years = text.match(/\b(19\d{2}|20\d{2})\b/g) || [];
    const cgpa = text.match(/\b(?:cgpa|gpa)\s*[:\-]?\s*(\d+(?:\.\d+)?(?:\s*\/\s*\d+(?:\.\d+)?)?)/i)?.[1]?.replace(/\s/g, "");
    const namedPercentage = text.match(/\b(?:percentage|percent)\s*[:=\-]?\s*(\d+(?:\.\d+)?%?)/i)?.[1]?.replace(/\s/g, "");
    const percentage = namedPercentage ? (namedPercentage.endsWith("%") ? namedPercentage : `${namedPercentage}%`) : (/%/.test(text) ? text.match(/\b(\d+(?:\.\d+)?%)/)?.[1] : undefined);
    const school = values.find((item, index) => index !== degreeIndex && !/\b(19\d{2}|20\d{2})\b|cgpa|gpa|percentage|percent|%/i.test(item)) || "";
    if (!degree || !school) return { error: "Please include at least the degree and college/institution. For example: PG: MCA, KSR College, 2023-2025, CGPA: 8.5." };
    const field = values.find((item, index) => index !== degreeIndex && item !== school && !/\b(19\d{2}|20\d{2})\b|cgpa|gpa|percent|%/i.test(item));
    parsed.push({
      school, degree, level: educationLevel(degree, label), field,
      start_date: years.length > 1 ? years[0] : undefined,
      end_date: years.length ? years[years.length - 1] : undefined, cgpa, percentage,
    });
  }
  return parsed.length ? parsed : { error: "Please add an education entry or type Skip." };
}
function mergeEducation(existing: ResumeCreateInput["education"] | undefined, updates: ResumeCreateInput["education"]) {
  const retained = (existing || []).filter((item) => !updates.some((update) => String(update.level || "").toUpperCase() === String(item.level || "").toUpperCase() && update.level));
  return [...retained, ...updates];
}
function parseCertificationInput(value: string): NonNullable<ResumeCreateInput["certifications"]> {
  return clean(value).replace(/^\s*certifications?\s*:\s*/i, "").split(/\s*(?:\n|;)\s*/).filter(Boolean).map((raw) => {
    const parts = raw.split(/\s+-\s+|\s*\|\s*|\s*,\s*/).map(clean).filter(Boolean);
    const name = parts[0] || clean(raw);
    const issue_date = raw.match(/\b(?:19|20)\d{2}\b/)?.[0];
    const issuer = parts.slice(1).find((part) => part !== issue_date && !/^credential\s*(?:id|#)/i.test(part));
    return { name, issuer, issue_date };
  }).filter((item) => Boolean(item.name));
}
function parseAchievementInput(value: string): NonNullable<ResumeCreateInput["achievements"]> {
  return clean(value).replace(/^\s*(?:achievements?|awards?|honors?)\s*:\s*/i, "").split(/\s*(?:\n|;)\s*/).filter(Boolean).map((raw) => {
    const parts = raw.split(/\s+-\s+|\s*\|\s*/).map(clean).filter(Boolean);
    return { title: parts[0] || clean(raw), description: parts.slice(1).join(" | ") || undefined, date: raw.match(/\b(?:19|20)\d{2}\b/)?.[0] };
  }).filter((item) => Boolean(item.title));
}
function normalizeDateInput(value: string) {
  const text = clean(value);
  const numeric = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (!numeric) return text;
  return `${numeric[1]}-${numeric[2].padStart(2, "0")}-${numeric[3].padStart(2, "0")}`;
}
function normalizeLocation(value: string) {
  const text = clean(value);
  const city = text.match(/city\s*:\s*([^,\n]+)/i)?.[1]?.trim();
  const country = text.match(/country\s*:\s*([^,\n]+)/i)?.[1]?.trim();
  return [city, country].filter(Boolean).join(", ") || text;
}
function optionalProfileUrl(value: string): { value?: string; error?: string } {
  const raw = clean(value);
  if (isSkip(raw) || /^(?:i\s+)?(?:do not|don't|dont) have (?:a |an )?(?:portfolio|website|profile)$/i.test(raw)) return {};
  if (/\s/.test(raw)) return { error: "Please enter one valid URL without spaces, or type Skip." };
  try {
    const url = new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`);
    if (!/^https?:$/.test(url.protocol) || !url.hostname.includes(".")) throw new Error("invalid URL");
    return { value: url.href.replace(/\/$/, "") };
  } catch {
    return { error: "Please enter a valid URL such as https://example.com, or type Skip." };
  }
}
const draftFieldSteps: Record<string, ResumeBuilderStep> = {
  title: "awaiting_title", name: "awaiting_name", email: "awaiting_email",
  phone: "awaiting_phone", location: "awaiting_location", city: "awaiting_location",
  role: "awaiting_role", summary: "awaiting_summary", skills: "awaiting_skills",
  experience: "awaiting_experience", education: "awaiting_education", project: "awaiting_project",
  certification: "awaiting_certifications", achievement: "awaiting_achievements",
  linkedin: "awaiting_linkedin", github: "awaiting_github", portfolio: "awaiting_portfolio",
};
function requestedDraftField(value: string) {
  const match = clean(value).toLowerCase().match(/^(?:i\s+(?:want|need)\s+to\s+)?(?:change|edit|update)\s+(?:my\s+)?([a-z ]+)$/);
  if (!match) return undefined;
  return Object.entries(draftFieldSteps).find(([field]) => match[1].includes(field))?.[1];
}

export const EXPERIENCE_PROMPT_TEXT = `Add an internship, job, freelance role, volunteer role, or other relevant practical experience.

Example:

Company: Acme Technologies
Role: Data Analyst
Duration: Jan 2024 – Present

Responsibilities:
• Developed Power BI dashboards for business reporting.
• Analyzed data using SQL and Excel.
• Automated recurring reports and generated business insights.

Type Skip if you do not want to add experience.
You can add or edit experience later from your resume editor.`;

function parseDuration(text: string) {
  const cleanText = clean(text);
  if (!cleanText) return { startDate: "", endDate: "", isCurrent: false };

  const rangeMatch = cleanText.match(/(.+?)\s*(?:–|—|-|\bto\b|\buntil\b)\s*(.+)/i);
  if (rangeMatch) {
    const start = clean(rangeMatch[1]);
    const end = normalizeDateInput(rangeMatch[2]);
    const isCurrent = /^(present|current|now)$/i.test(end);
    return { startDate: start, endDate: end, isCurrent };
  }

  if (/\b(present|current|now)\b/i.test(cleanText)) {
    const start = clean(cleanText.replace(/\b(present|current|now)\b/gi, "").replace(/^[–—-]/, "").trim());
    return { startDate: start, endDate: "Present", isCurrent: true };
  }

  return { startDate: cleanText, endDate: "", isCurrent: false };
}

function cleanBullets(text: string) {
  if (!text) return "";
  return text
    .split(/\r?\n/)
    .map((line) => line.trim().replace(/^[•\-\*]\s*/, "").trim())
    .filter(Boolean)
    .join(" • ");
}

function isNewEntryBlock(block: string) {
  const c = clean(block);
  if (!c) return false;
  if (/^(?:Company|Employer|Organization|Role|Job Title|Position|Title)\s*:/i.test(c)) return true;
  if (/(?:^|\n)\s*(?:Company|Employer|Organization)\s*:/i.test(c)) return true;
  if (/(?:I\s+)?(?:worked|interned|served)\s+as\b/i.test(c)) return true;
  const lines = c.split(/\r?\n/).map(clean).filter(Boolean);
  const hasDateRange = lines.some((l) => /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})\b.*?(?:–|—|-|\bto\b|\buntil\b).*?(?:Present|Current|Now|\d{4})/i.test(l));
  if (hasDateRange && lines.length >= 2) return true;
  if (lines.length >= 2 && /^.+?\s+(?:at|@)\s+.+$/i.test(lines[0])) return true;
  return false;
}

function splitExperienceEntries(input: string): string[] {
  const text = clean(input);
  if (!text) return [];

  // Multiple entries separated by "Company:" or "Employer:"
  const companyMatches = [...text.matchAll(/(?:^|\n)\s*(?:Company|Employer|Organization)\s*:/gi)];
  if (companyMatches.length > 1) {
    const entries: string[] = [];
    for (let i = 0; i < companyMatches.length; i++) {
      const startIndex = companyMatches[i].index!;
      const endIndex = i + 1 < companyMatches.length ? companyMatches[i + 1].index! : text.length;
      entries.push(text.slice(startIndex, endIndex).trim());
    }
    return entries.filter(Boolean);
  }

  // Semicolon-separated entries
  if (text.includes(";") && (text.includes("|") || text.includes("Role:") || !text.includes("\n"))) {
    return text.split(/\s*;\s*/).filter(Boolean);
  }

  // Blocks separated by blank lines
  const rawBlocks = text.split(/\n\s*\n+/).map(clean).filter(Boolean);
  const mergedBlocks: string[] = [];
  for (const block of rawBlocks) {
    if (mergedBlocks.length > 0 && !isNewEntryBlock(block)) {
      mergedBlocks[mergedBlocks.length - 1] += "\n\n" + block;
    } else {
      mergedBlocks.push(block);
    }
  }

  if (mergedBlocks.length > 1) {
    return mergedBlocks;
  }

  return [text];
}

function parseSingleExperience(raw: string) {
  const text = clean(raw);
  if (!text) return null;

  // 1. Pipe format (backward compatibility)
  if (text.includes("|") && !text.includes("Company:")) {
    const parts = text.split("|").map(clean);
    if (parts.length >= 2) {
      const company = parts[0];
      const role = parts[1];
      const startDate = parts[2] ? normalizeDateInput(parts[2]) : "";
      const endDate = parts[3] ? normalizeDateInput(parts[3]) : "";
      const isCurrent = /^(present|current|now)$/i.test(endDate);
      const rawInput = parts.slice(4).join(" | ").trim();
      return { company, role, start_date: startDate, end_date: endDate, is_current: isCurrent, raw_input: rawInput };
    }
  }

  // 2. Structured key-value format (Format A)
  const companyMatch = text.match(/(?:^|\n)\s*(?:Company|Employer|Organization)\s*:\s*([^\n]+)/i);
  const roleMatch = text.match(/(?:^|\n)\s*(?:Role|Job Title|Position|Title)\s*:\s*([^\n]+)/i);
  const durationMatch = text.match(/(?:^|\n)\s*(?:Duration|Dates?|Period|Tenure)\s*:\s*([^\n]+)/i);
  const respMatch = text.match(/(?:^|\n)\s*(?:Responsibilities|Achievements|Responsibilities\s*&\s*Achievements|Key Responsibilities|Key Achievements|Description|Duties)\s*:\s*([\s\S]*)/i);

  if (companyMatch && roleMatch) {
    const company = clean(companyMatch[1]);
    const role = clean(roleMatch[1]);
    const { startDate, endDate, isCurrent } = parseDuration(durationMatch ? durationMatch[1] : "");
    const rawInput = respMatch ? cleanBullets(respMatch[1]) : "";
    return {
      company,
      role,
      start_date: startDate,
      end_date: endDate,
      is_current: isCurrent,
      raw_input: rawInput,
    };
  }

  // 3. Natural narrative paragraph (Format C)
  const sentenceMatch = text.match(
    /(?:I\s+)?(?:worked|interned|served|work)\s+as\s+(?:an?\s+)?(.+?)\s+(?:at|for|with)\s+(.+?)(?:\s+(?:from|since)\s+|\s*,\s*)(.+?)(?:\.|$)([\s\S]*)/i
  );
  if (sentenceMatch) {
    const role = clean(sentenceMatch[1]);
    const company = clean(sentenceMatch[2]);
    const dateAndMore = clean(sentenceMatch[3]);
    const trailing = clean(sentenceMatch[4]);

    let startDate = "";
    let endDate = "";
    let isCurrent = false;

    if (/\b(?:and\s+)?(?:I\s+am\s+)?currently\s+working\s+there\b/i.test(dateAndMore) || /\bpresent\b/i.test(dateAndMore)) {
      isCurrent = true;
      endDate = "Present";
      startDate = clean(dateAndMore.replace(/\b(?:and\s+)?(?:I\s+am\s+)?currently\s+working\s+there\b/i, "").replace(/\bpresent\b/i, "").replace(/\bto\b/i, "").trim());
    } else {
      const dates = parseDuration(dateAndMore);
      startDate = dates.startDate;
      endDate = dates.endDate;
      isCurrent = dates.isCurrent;
    }

    let rawInput = trailing;
    const respExtract = trailing.match(/(?:My\s+responsibilities\s+include|Responsibilities\s+include|I\s+worked\s+on|Worked\s+on|I\s+developed|Developed|Responsibilities:?)\s*([\s\S]*)/i);
    if (respExtract) {
      rawInput = clean(respExtract[1]);
    } else if (trailing.startsWith(".")) {
      rawInput = clean(trailing.slice(1));
    }

    return {
      company,
      role,
      start_date: startDate,
      end_date: endDate,
      is_current: isCurrent,
      raw_input: rawInput,
    };
  }

  // 4. Concise role at company line (Format D / Format B)
  const lines = text.split(/\r?\n/).map(clean).filter(Boolean);
  if (lines.length >= 2) {
    const atMatch = lines[0].match(/^(.+?)\s+(?:at|@)\s+(.+)$/i);
    if (atMatch) {
      const role = clean(atMatch[1]);
      const company = clean(atMatch[2]);
      const { startDate, endDate, isCurrent } = lines[1] ? parseDuration(lines[1]) : { startDate: "", endDate: "", isCurrent: false };
      const rawInput = lines.slice(2).join(" • ");
      return { company, role, start_date: startDate, end_date: endDate, is_current: isCurrent, raw_input: rawInput };
    }

    if (lines.length >= 3) {
      const dates = parseDuration(lines[2]);
      if (dates.startDate) {
        const company = lines[0];
        const role = lines[1];
        const rawInput = lines.slice(3).join(" • ");
        return { company, role, start_date: dates.startDate, end_date: dates.endDate, is_current: dates.isCurrent, raw_input: rawInput };
      }
    }
  }

  return null;
}

export function parseExperienceInput(value: string): Array<{
  company: string;
  role: string;
  start_date?: string;
  end_date?: string;
  is_current?: boolean;
  raw_input?: string;
}> {
  const entries = splitExperienceEntries(value);
  const result: Array<{
    company: string;
    role: string;
    start_date?: string;
    end_date?: string;
    is_current?: boolean;
    raw_input?: string;
  }> = [];
  for (const entry of entries) {
    const parsed = parseSingleExperience(entry);
    if (parsed && parsed.company && parsed.role) {
      result.push(parsed);
    }
  }
  return result;
}

function draftFieldPrompt(field: string, draft: ResumeDraft = {}) {
  const prompts: Record<string, string> = {
    title: "What title should this resume use? For example: Python Developer Resume.",
    name: `What full name should appear on the resume? Current: ${draft.name || "not set"}.`,
    email: `What email should appear on the resume? Current: ${draft.email || "not set"}.`,
    phone: "What phone number should appear? Type Skip to leave it blank.",
    location: "What city and country should appear? For example: Gobi, India. Type Skip to leave it blank.",
    role: "What role are you targeting? For example: Python Developer.",
    summary: "Write a short summary, or write a few facts and I will help improve it later. Type Skip to leave it blank.",
    skills: "List skills separated by commas. For example: Python, Flask, SQL, React.",
    experience: EXPERIENCE_PROMPT_TEXT,
    education: "Add education in a short format, for example: PG: MCA, KSR College, Computer Applications, 2023-2025, CGPA: 8.5. You can add UG and PG entries separated by semicolons. Type Skip to omit it.",
    project: "Add a project: Project title | What you built and its outcome. Type Skip to omit it.",
    certifications: "Add certifications one per line. Example: Microsoft Power BI Data Analyst Associate - Microsoft - 2025. Type Skip to omit them.",
    achievements: "Add achievements one per line. Example: Hackathon Winner - First place in a college hackathon - 2025. Type Skip to omit them.",
    linkedin: "Please provide your LinkedIn profile URL, or type Skip.",
    github: "Please provide your GitHub profile URL, or type Skip.",
    portfolio: "Please provide your portfolio or personal website URL, or type Skip.",
  };
  return prompts[field] || "What would you like to change?";
}
function formatEditProposal(proposal: ResumeEditProposal) {
  const changes = proposal.changes.length
    ? proposal.changes.map((item) => `• ${item}`).join("\n")
    : "• No supported changes were found.";
  const warnings = proposal.warnings.length
    ? `\n\nPlease review:\n${proposal.warnings.map((item) => `• ${item}`).join("\n")}`
    : "";
  return `Here is the proposed resume update. Nothing has been changed yet.\n\nChanges:\n${changes}${warnings}\n\nChoose Apply changes to save it, or Revise request to try again.`;
}
export interface AtsReadinessAudit {
  isMinimal: boolean;
  scoreEstimate: string;
  recommendations: string[];
}

export function evaluateAtsReadiness(draft: ResumeDraft): AtsReadinessAudit {
  const recommendations: string[] = [];
  const projectCount = (draft.projects || []).length;
  const skillCount = (draft.skills || []).length;
  const experienceCount = (draft.experience || []).length;
  const certCount = (draft.certifications || []).length;
  const achCount = (draft.achievements || []).length;
  const summaryLength = (draft.summary || "").trim().length;
  const links = draft.links || [];
  const hasLinkedIn = links.some((l) => /^LinkedIn\s*:/i.test(l));
  const hasGitHub = links.some((l) => /^GitHub\s*:/i.test(l));

  if (projectCount === 0) {
    recommendations.push("Projects (0 added): Add at least 1–2 projects to demonstrate practical technical skills.");
  } else if (projectCount === 1) {
    recommendations.push("Projects (1 added): Add 1–2 more relevant projects. Recruiters and ATS algorithms favor candidate profiles with 2+ documented projects.");
  }

  if (skillCount < 5) {
    recommendations.push(`Skills (${skillCount} added): List at least 6–8 key technical and domain skills to match automated ATS keyword filters.`);
  }

  if (draft.experienceLevel === "experienced" && experienceCount === 0) {
    recommendations.push("Experience (0 added): Experienced resumes require at least one prior employment or consulting role.");
  }

  if (summaryLength < 30) {
    recommendations.push("Professional Summary: A 2–3 sentence role-focused summary improves keyword density and executive recruiter match.");
  }

  if (!hasLinkedIn && !hasGitHub) {
    recommendations.push("Professional Links: Adding LinkedIn or GitHub profiles verifies candidate credentials and provides proof of work.");
  }

  if (certCount === 0 && achCount === 0) {
    recommendations.push("Certifications / Achievements: Industry certifications or awards give your resume an edge against other applicants.");
  }

  const isMinimal = recommendations.length >= 2 || projectCount <= 1 || skillCount < 4;
  const scoreEstimate = isMinimal ? (recommendations.length >= 3 ? "45–60/100" : "60–72/100") : "85–95/100";

  return {
    isMinimal,
    scoreEstimate,
    recommendations,
  };
}

function enrichmentChoiceMessage(draft: ResumeDraft): ResumeBuilderMessage {
  const audit = evaluateAtsReadiness(draft);
  const options: ChatOption[] = [];
  if ((draft.projects || []).length < 2) {
    options.push({ label: "+ Add another project", value: "enrich_project", description: "Add 1–2 more projects to show your technical depth." });
  }
  if ((draft.skills || []).length < 6) {
    options.push({ label: "+ Add more skills", value: "enrich_skills", description: "Add key tools, languages, and technical keywords." });
  }
  const hasLinkedIn = (draft.links || []).some((l) => /^LinkedIn\s*:/i.test(l));
  const hasGitHub = (draft.links || []).some((l) => /^GitHub\s*:/i.test(l));
  if (!hasLinkedIn || !hasGitHub) {
    options.push({ label: "+ Add professional links", value: "enrich_links", description: "Add LinkedIn or GitHub to verify your work." });
  }
  if (!(draft.certifications || []).length) {
    options.push({ label: "+ Add certifications", value: "enrich_certifications", description: "Add industry certificates or licenses." });
  }
  if (!(draft.achievements || []).length) {
    options.push({ label: "+ Add achievements", value: "enrich_achievements", description: "Add honors, competitions, or awards." });
  }
  if (draft.experienceLevel === "experienced" && !(draft.experience || []).length) {
    options.push({ label: "+ Add experience", value: "enrich_experience", description: "Add previous roles and work history." });
  }
  if (!draft.summary || draft.summary.trim().length < 30) {
    options.push({ label: "+ Enhance summary", value: "enrich_summary", description: "Expand your professional summary." });
  }
  options.push({ label: "Create my resume now", value: "create_now", description: "Proceed to create your resume with current details." });
  options.push({ label: "Back to Review", value: "back_to_review", description: "Return to the review summary." });

  return {
    text: `Which section would you like to enrich first for a high ATS score?\n\nRecommended improvements:\n${audit.recommendations.map((r) => `• ${r}`).join("\n")}`,
    options,
  };
}

export function buildAtsScorecardMessage(
  fileName: string,
  targetRole: string,
  score: number,
  analysis?: Record<string, unknown>,
  roleAnalysis?: { matched_skills?: string[]; recommended_skills_to_learn?: string[]; missing_information?: string[] },
  aiGenerated = true,
): ResumeBuilderMessage {
  const rating =
    score >= 85 ? "🟢 High ATS Match (Optimal ranking)" :
    score >= 70 ? "🟡 Good ATS Match (Competitive candidate)" :
    "🟠 ATS Advisory (Room for enrichment)";

  const matchedSkills: string[] = [];
  const missingSkills: string[] = [];

  if (analysis?.skills && typeof analysis.skills === "object") {
    const s = analysis.skills as Record<string, unknown>;
    const matchedReq = Array.isArray(s.matched_required) ? s.matched_required : [];
    const matchedPref = Array.isArray(s.matched_preferred) ? s.matched_preferred : [];
    for (const item of [...matchedReq, ...matchedPref]) {
      const name = typeof item === "string" ? item : (item as { skill?: string })?.skill;
      if (name && !matchedSkills.includes(name)) matchedSkills.push(name);
    }
    const missReq = Array.isArray(s.missing_required) ? s.missing_required : [];
    const missPref = Array.isArray(s.missing_preferred) ? s.missing_preferred : [];
    for (const item of [...missReq, ...missPref]) {
      const name = typeof item === "string" ? item : (item as { skill?: string })?.skill;
      if (name && !missingSkills.includes(name)) missingSkills.push(name);
    }
  }
  if (roleAnalysis?.matched_skills) {
    for (const s of roleAnalysis.matched_skills) {
      if (!matchedSkills.includes(s)) matchedSkills.push(s);
    }
  }
  if (roleAnalysis?.recommended_skills_to_learn) {
    for (const s of roleAnalysis.recommended_skills_to_learn) {
      if (!missingSkills.includes(s)) missingSkills.push(s);
    }
  }

  const breakdownLines: string[] = [];
  if (analysis?.breakdown && typeof analysis.breakdown === "object") {
    const bd = analysis.breakdown as Record<string, { label?: string; earned?: number; maximum?: number; pointsEarned?: number; maxPoints?: number }>;
    for (const [key, cat] of Object.entries(bd)) {
      const label = cat.label || key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
      const earned = cat.earned ?? cat.pointsEarned;
      const max = cat.maximum ?? cat.maxPoints;
      if (earned !== undefined && max !== undefined && max > 0) {
        breakdownLines.push(`• ${label}: ${Math.round(earned)}/${max} pts`);
      }
    }
  }

  const sections: string[] = [
    `🎯 **ATS Match Score: ${score}/100**\n**Rating:** ${rating}\n**Target Role:** ${targetRole}`,
    aiGenerated
      ? `✨ **AI Resume Tailoring Complete:**\nYour resume has been tailored by AI for the **${targetRole}** role. Professional summary, target skills, and project/experience impact bullets have been optimized.`
      : `📄 **Resume Imported:** ${fileName}`,
  ];

  if (matchedSkills.length > 0) {
    sections.push(`✅ **Matched Skills for ${targetRole}:**\n${matchedSkills.slice(0, 8).join(", ")}`);
  }
  if (missingSkills.length > 0) {
    sections.push(`💡 **Skills to Add or Learn for ${targetRole}:**\n${missingSkills.slice(0, 8).join(", ")}`);
  }
  if (breakdownLines.length > 0) {
    sections.push(`📊 **ATS Category Breakdown:**\n${breakdownLines.slice(0, 6).join("\n")}`);
  }

  sections.push("You can choose a template to download your PDF, edit the resume with AI, or enrich specific sections.");

  const options: ChatOption[] = [
    { label: "Choose template & download", value: "choose_template", description: "Pick a template to preview and download your PDF resume." },
    { label: "Edit with AI", value: "edit_resume", description: "Describe any change you want in plain language." },
    { label: "⚡ Enrich for High ATS", value: "enrich_ats", description: "Add missing projects, skills, or links to maximize your ATS score." },
    ...restartOption,
  ];

  return {
    text: sections.join("\n\n"),
    options,
  };
}

function reviewMessage(draft: ResumeDraft): ResumeBuilderMessage {
  const pagePlan = draft.experienceLevel === "fresher" ? "One-page ATS resume" : "Up to two-page ATS resume";
  const education = draft.education || [];
  const ugCount = education.filter((item) => String(item.level || "").toUpperCase() === "UG" || /\b(bca|b\.?sc|b\.?tech|b\.?e|bba|b\.?a|bachelor)\b/i.test(String(item.degree || ""))).length;
  const pgCount = education.filter((item) => String(item.level || "").toUpperCase() === "PG" || /\b(mca|m\.?sc|m\.?tech|mba|m\.?a|master)\b/i.test(String(item.degree || ""))).length;
  const links = draft.links || [];
  const linkStatus = (label: string) => links.some((item) => new RegExp(`^${label}\\s*:`, "i").test(item)) ? "provided" : "not added";
  const baseText = `Please review your details:\n• ${draft.name} — ${draft.email}\n• Target role: ${draft.targetRole}\n• Career level: ${draft.experienceLevel === "fresher" ? "Fresher" : "Experienced"} (${pagePlan})\n• Skills: ${(draft.skills || []).join(", ") || "Not added"}\n• Experience: ${draft.experience?.length || 0} entry\n• Education: UG ${ugCount} entry; PG ${pgCount} entry\n• Projects: ${draft.projects?.length || 0} entry\n• Certifications: ${draft.certifications?.length || 0} entry\n• Achievements: ${draft.achievements?.length || 0} entry\n• LinkedIn: ${linkStatus("LinkedIn")}\n• GitHub: ${linkStatus("GitHub")}\n• Portfolio: ${linkStatus("Portfolio")}`;

  const audit = evaluateAtsReadiness(draft);

  if (audit.isMinimal) {
    const advisoryText = `\n\n⚠️ ATS Quality Advisory (Minimal Information Detected):\nThese are all the details provided so far. With minimal details, an automated ATS scanner typically rates this resume around ${audit.scoreEstimate}.\nTo achieve a high ATS score (85+) and rank among top candidates for ${draft.targetRole || "your target role"}, we recommend:\n${audit.recommendations.map((r) => `• ${r}`).join("\n")}\n\nWould you like to enrich these sections now to ensure a high ATS score for your best resume, or create the resume as is?`;
    return {
      text: `${baseText}${advisoryText}`,
      options: [
        { label: "⚡ Enrich for High ATS (Recommended)", value: "enrich_ats", description: "Add missing projects, skills, or links to maximize your ATS score." },
        { label: "Create my resume now", value: "create_now", description: "Create your editable resume with these details." },
        ...restartOption,
      ],
    };
  }

  return {
    text: `${baseText}\n\n✅ High ATS Score Ready:\nYour details provide strong coverage across skills, projects, and credentials for optimal ATS ranking (Estimated: ${audit.scoreEstimate}).\n\nEverything looks right?`,
    options: [
      { label: "Create my resume", value: "create_now", description: "Create your editable resume with these details." },
      ...restartOption,
    ],
  };
}

async function createFromDraft(state: ResumeBuilderFlowState, user: User): Promise<ResumeBuilderFlowResult> {
  const draft = state.draft;
  if (!draft?.title || !draft.name || !draft.email || !draft.targetRole || !draft.experienceLevel) {
    return { state: { ...state, step: "error", error: "Your required resume details are incomplete." }, messages: [{ text: "Your required details are incomplete. Please choose Start over and complete the required fields.", options: restartOption }] };
  }
  if (!hasUndergraduateEducation(draft.education)) {
    return {
      state: { ...state, step: "awaiting_education", pendingField: "education.ug" },
      messages: [{ text: "Undergraduate education is required to generate your resume. Add at least your UG degree and college; postgraduate education remains optional.", options: skipOption }],
    };
  }
  if (!(draft.projects?.length || draft.experience?.length)) {
    return {
      state: { ...state, step: "awaiting_project" },
      messages: [{ text: "Add at least one project or experience entry before generating your resume. Short project details are enough for AI to improve later." }],
    };
  }
  try {
    const resume = await createResume(user.id, {
      title: draft.title,
      target_role: draft.targetRole,
      experience_level: draft.experienceLevel,
      summary: draft.summary || "",
      personal_info: { name: draft.name, email: draft.email, phone: draft.phone, location: draft.location, links: draft.links || [] },
      declaration: "I hereby declare that the information provided in this resume is true and accurate to the best of my knowledge and belief.",
      declaration_enabled: true,
      skills: (draft.skills || []).map((skill_name) => ({ skill_name })),
      experience: draft.experience || [],
      education: draft.education || [],
      projects: draft.projects || [],
      certifications: draft.certifications || [],
      achievements: draft.achievements || [],
    });
    const id = Number(resume.id);
    return { state: { ...state, step: "reviewing", resumeId: id, resumeTitle: String(resume.title || draft.title) }, messages: [{ text: "Your resume has been saved from the details you verified. You can edit it in plain language, then choose Generate final wording to create the complete target-role-focused version.", options: reviewOptions }] };
  } catch (error) {
    return { state: { ...state, step: "confirming", error: (error as Error).message }, messages: [{ text: `I couldn’t create the resume: ${(error as Error).message}. Your details are still saved in this chat.`, options: [{ label: "Try creating again", value: "create_now" }, ...restartOption] }] };
  }
}

function replaceProfessionalLink(resume: Record<string, unknown>, label: "LinkedIn" | "GitHub" | "Portfolio", value: string) {
  const personalInfo = (resume.personal_info && typeof resume.personal_info === "object")
    ? resume.personal_info as Record<string, unknown>
    : {};
  const links = Array.isArray(personalInfo.links) ? personalInfo.links.filter((link): link is string => typeof link === "string") : [];
  const pattern = label === "Portfolio" ? /^(portfolio|website)\s*:/i : new RegExp(`^${label}\\s*:`, "i");
  return {
    ...resume,
    personal_info: {
      ...personalInfo,
      links: isSkip(value) ? links : [...links.filter((link) => !pattern.test(link)), `${label}: ${clean(value)}`],
    },
  };
}

async function saveImportedProfessionalLink(
  state: ResumeBuilderFlowState,
  user: User,
  label: "LinkedIn" | "GitHub" | "Portfolio",
  value: string,
  nextStep: ResumeBuilderStep,
  nextPrompt: string,
): Promise<ResumeBuilderFlowResult> {
  if (!state.resumeId) return { state, messages: [{ text: "The imported resume is no longer available. Please upload it again." }] };
  const normalized = optionalProfileUrl(value);
  if (normalized.error) return { state, messages: [{ text: normalized.error, options: skipOption }] };
  try {
    const current = await getResume(user.id, state.resumeId);
    const saved = await updateResume(user.id, state.resumeId, replaceProfessionalLink(current, label, normalized.value || "skip"));
    return {
      state: { ...state, step: nextStep, resumeTitle: String(saved.title || state.resumeTitle) },
      messages: [{ text: nextPrompt, options: skipOption }],
    };
  } catch (error) {
    return { state, messages: [{ text: `I could not save that ${label} value: ${(error as Error).message}. Please try again.`, options: skipOption }] };
  }
}

async function generateVerifiedResume(state: ResumeBuilderFlowState, user: User): Promise<ResumeBuilderFlowResult> {
  if (!state.resumeId) {
    return { state, messages: [{ text: "There is no saved resume to generate yet. Create or upload a resume first." }] };
  }
  try {
    const current = await getResume(user.id, state.resumeId);
    const currentEducation = Array.isArray(current.education) ? current.education as ResumeCreateInput["education"] : [];
    const isExperienced = String(current.experience_level || state.draft?.experienceLevel || "").toLowerCase() === "experienced";
    const hasAnyEducation = currentEducation.length > 0;
    const skipEducationRequested = Boolean(state.draft?.skipEducation);

    if (!isExperienced && !hasUndergraduateEducation(currentEducation) && !hasAnyEducation && !skipEducationRequested) {
      return {
        state: { ...state, step: "reviewing" },
        messages: [{ text: "Undergraduate education is recommended for a fresher resume before final wording is generated. Add or correct your education details using Edit with AI, or type 'school is no problem' to proceed without it.", options: reviewOptions }],
      };
    }
    const targetRole = String(current.target_role || state.draft?.targetRole || "");
    const generated = await generateImportedResume(user.id, current, targetRole, state.draft?.jobDescription || "");
    if (!generated.resume) throw new Error("AI generation did not return an editable resume.");
    const saved = await updateResume(user.id, state.resumeId, generated.resume);
    let atsScore = state.atsScore;
    try {
      const analysis = await analyzeSavedResume(user.id, state.resumeId, state.draft?.jobDescription || "", targetRole);
      const score = Number((analysis.score as { normalized_score?: number } | undefined)?.normalized_score);
      if (Number.isFinite(score)) atsScore = score;
    } catch {
      // The complete verified resume remains saved even if a later ATS refresh fails.
    }
    const templates = await listResumeTemplates();
    const templateOptions: ChatOption[] = templates.map((template) => ({
      label: template.name,
      value: `template:${template.id}`,
      description: template.description || "Apply this template to the preview and final PDF.",
    }));
    const recommendations = generated.role_analysis?.recommended_skills_to_learn || [];
    const missingInformation = generated.role_analysis?.missing_information || [];
    const analysisNote = recommendations.length || missingInformation.length
      ? `\n\nSuggestions only (not added to your resume):${recommendations.length ? `\n• Consider learning: ${recommendations.join(", ")}` : ""}${missingInformation.length ? `\n• Add evidence for: ${missingInformation.join(", ")}` : ""}`
      : "";
    return {
      state: { ...state, step: "awaiting_template", resumeTitle: String(saved.title || state.resumeTitle), atsScore },
      messages: [{ text: `Your complete, source-grounded resume wording has been generated and ATS has been refreshed. Choose a resume template for your preview and final PDF.${analysisNote}`, options: templateOptions }],
    };
  } catch (error) {
    return { state: { ...state, step: "reviewing" }, messages: [{ text: `I could not generate the complete resume wording: ${(error as Error).message}. Your verified resume data is still saved and unchanged.`, options: reviewOptions }] };
  }
}

export async function openResumeBuilderChat(user: User): Promise<ResumeBuilderFlowResult> {
  const state = createInitialResumeBuilderState();
  try { await ensureResumeProfile(user.id, user.name, user.email); return { state, messages: [{ text: `Hi ${user.name.split(" ")[0]}! Would you like to create a new resume or upload one to improve?`, options: choices }] }; }
  catch (error) { return { state: { ...state, step: "error", error: (error as Error).message }, messages: [{ text: `I could not initialize Resume Builder: ${(error as Error).message}`, options: [{ label: "Try again", value: "retry" }] }] }; }
}

export function isCreateResumeIntent(value: string): boolean {
  const norm = clean(value).toLowerCase().replace(/resue/g, "resume");
  return (
    norm === "create_resume" ||
    norm === "new" ||
    norm === "create a resume" ||
    norm === "create resume" ||
    norm === "create my resume" ||
    norm === "i want to create a resume" ||
    norm === "make my resume" ||
    norm === "build my resume" ||
    norm === "create" ||
    norm.includes("create a resume") ||
    norm.includes("create my resume") ||
    norm.includes("create resume")
  );
}

export function isGenerateResumeIntent(value: string): boolean {
  const norm = clean(value).toLowerCase().replace(/resue/g, "resume");
  return (
    norm === "generate_resume" ||
    norm === "generate resume" ||
    norm === "generate my resume" ||
    norm === "generate my resume now" ||
    norm === "generate the resume" ||
    norm === "generate me resume" ||
    norm === "generate" ||
    norm.includes("generate my resume") ||
    norm.includes("generate me resume") ||
    norm.includes("generate resume") ||
    norm.includes("school is no problem") ||
    norm.includes("education is no problem")
  );
}

export function isUploadResumeIntent(value: string): boolean {
  const norm = clean(value).toLowerCase().replace(/resue/g, "resume");
  return (
    norm === "upload_resume" ||
    norm === "upload" ||
    norm === "upload an existing resume" ||
    norm === "upload resume" ||
    norm === "upload existing resume" ||
    norm.includes("upload an existing resume") ||
    norm.includes("upload resume")
  );
}

export function isRetryUploadIntent(value: string): boolean {
  const norm = clean(value).toLowerCase();
  return (
    norm === "retry_upload" ||
    norm === "retry" ||
    norm === "try again" ||
    norm === "try_again" ||
    norm.includes("retry upload") ||
    norm.includes("try again")
  );
}

export async function handleResumeBuilderText(state: ResumeBuilderFlowState, user: User, value: string): Promise<ResumeBuilderFlowResult> {
  if (value === "restart" || clean(value).toLowerCase() === "start over") return openResumeBuilderChat(user);

  if (isRetryUploadIntent(value)) {
    if (state.draft?.targetRole) {
      return {
        state: { ...state, step: "awaiting_upload", error: undefined },
        messages: [{
          text: `Attach your PDF, DOC, DOCX, or TXT resume. I’ll analyze it against the ${state.draft.targetRole} role and create an editable ${state.draft.experienceLevel === "fresher" ? "one-page" : "up-to-two-page"} ATS version.`,
        }],
      };
    }
    return {
      state: { ...state, step: "awaiting_upload_role", error: undefined },
      messages: [{ text: "What role are you targeting with this resume? For example: Data Analyst or Python Developer." }],
    };
  }

  if (isCreateResumeIntent(value)) {
    if (state.step === "awaiting_experience_level") {
      return { state, messages: [{ text: "Before we begin, which best describes you? This sets the right resume length and section priorities.", options: [{ label: "Fresher / student", value: "fresher", description: "A concise, one-page resume focused on education, projects, skills, and internships." }, { label: "Experienced professional", value: "experienced", description: "A resume designed for up to two pages, with room for career impact and achievements." }] }] };
    }
    const preservedTargetRole = state.draft?.targetRole;
    return {
      state: { ...state, step: "awaiting_experience_level", error: undefined, draft: { targetRole: preservedTargetRole } },
      messages: [{
        text: "Before we begin, which best describes you? This sets the right resume length and section priorities.",
        options: [
          { label: "Fresher / student", value: "fresher", description: "A concise, one-page resume focused on education, projects, skills, and internships." },
          { label: "Experienced professional", value: "experienced", description: "A resume designed for up to two pages, with room for career impact and achievements." },
        ],
      }],
    };
  }

  if (isUploadResumeIntent(value)) {
    return {
      state: { ...state, step: "awaiting_upload_role", error: undefined, draft: {} },
      messages: [{ text: "What role are you targeting with this resume? For example: Data Analyst or Python Developer." }],
    };
  }

  if (isGenerateResumeIntent(value)) {
    const isNoProblem = /school is no problem|education is no problem|no problem/i.test(value);
    const effectiveState = isNoProblem ? { ...state, draft: { ...state.draft, skipEducation: true } } : state;
    if (effectiveState.resumeId) {
      return generateVerifiedResume(effectiveState, user);
    }
    if (state.step === "confirming") {
      return createFromDraft(state, user);
    }
    if (state.step === "awaiting_education" || state.step === "awaiting_education_more") {
      const next = updateDraft(state, {}, (state.draft?.projects?.length || 0) > 0 ? "confirming" : "awaiting_project");
      if (next.step === "confirming") {
        return { state: next, messages: [reviewMessage(next.draft || {})] };
      }
      return {
        state: next,
        messages: [{
          text: "No problem, we'll continue without education details. Add your most relevant project in this format:\nProject Title | Technologies used | What you built and its impact\n\nType Skip if you do not want to add projects.",
          options: skipOption,
        }],
      };
    }
    if (state.draft && (state.draft.name || state.draft.targetRole || (state.draft.skills?.length || 0) > 0)) {
      return createFromDraft(state, user);
    }
  }

  const command = clean(value).toLowerCase();

  // Declaration visibility is a reversible presentation choice. Handle it
  // directly so the candidate does not need an AI rewrite or lose the saved
  // declaration text just to hide it from this resume version.
  const declarationVisibility = command.match(/^(show|enable|hide|disable)\s+(?:the\s+)?declaration$/);
  if (declarationVisibility && state.resumeId && ["reviewing", "completed"].includes(state.step)) {
    const enabled = ["show", "enable"].includes(declarationVisibility[1]);
    try {
      const current = await getResume(user.id, state.resumeId);
      await updateResume(user.id, state.resumeId, { ...current, declaration_enabled: enabled });
      return {
        state,
        messages: [{ text: enabled ? "Your declaration will appear in the resume preview and PDF." : "Your declaration is hidden from the resume preview and PDF. Its saved text was kept." }],
      };
    } catch (error) {
      return { state, messages: [{ text: `I could not update declaration visibility: ${(error as Error).message}.` }] };
    }
  }

  // A link replacement is deterministic, so a completed resume does not need
  // an unnecessary LLM edit proposal just to change its portfolio address.
  const portfolioEdit = clean(value).match(/(?:portfolio|website)(?:\s+(?:link|url))?\s*(?:is\s+now|is|to)?\s*((?:https?:\/\/|www\.)\S+|[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(?:\/\S*)?)/i);
  if (portfolioEdit && state.resumeId && ["reviewing", "completed"].includes(state.step)) {
    const result = await saveImportedProfessionalLink(state, user, "Portfolio", portfolioEdit[1], state.step, "");
    if (result.state.step !== state.step) return result;
    return {
      ...result,
      messages: [{ text: "Your portfolio link was updated. Your resume preview and PDF will use the new link." }],
    };
  }

  const draftField = requestedDraftField(value);
  if (draftField && !["reviewing", "awaiting_edit_instruction", "awaiting_edit_confirmation"].includes(state.step)) {
    return { state: { ...state, step: draftField }, messages: [{ text: draftFieldPrompt(draftField.replace("awaiting_", ""), state.draft) }] };
  }
  if (command === "back" && state.step.startsWith("awaiting_")) {
    const previousSteps: Partial<Record<ResumeBuilderStep, ResumeBuilderStep>> = {
      awaiting_title: "awaiting_experience_level", awaiting_name: "awaiting_title", awaiting_email: "awaiting_name",
      awaiting_phone: "awaiting_email", awaiting_location: "awaiting_phone", awaiting_role: "awaiting_location",
      awaiting_summary: "awaiting_role", awaiting_skills: "awaiting_summary", awaiting_experience: "awaiting_skills",
      awaiting_experience_more: "awaiting_experience",
      awaiting_education: "awaiting_experience", awaiting_education_more: "awaiting_education",
      awaiting_project: "awaiting_education", awaiting_project_more: "awaiting_project",
      awaiting_linkedin: "awaiting_project", awaiting_github: "awaiting_linkedin", awaiting_portfolio: "awaiting_github",
      awaiting_certifications: "awaiting_portfolio", awaiting_certifications_more: "awaiting_certifications",
      awaiting_achievements: "awaiting_certifications", awaiting_achievements_more: "awaiting_achievements",
      awaiting_enrichment_choice: "confirming",
    };
    const previous = previousSteps[state.step];
    if (previous) return { state: { ...state, step: previous }, messages: [{ text: `Okay — ${draftFieldPrompt(previous.replace("awaiting_", "").replace("_more", ""), state.draft)}` }] };
  }

  if (state.step === "awaiting_edit_confirmation") {
    if (["apply_edit", "ok", "okay", "confirm", "yes", "apply"].includes(command)) {
      if (!state.resumeId || !state.pendingEdit?.resume) {
        return { state: { ...state, step: "reviewing", pendingEdit: undefined }, messages: [{ text: "That edit proposal expired. Describe the change again and I will prepare a new review.", options: reviewOptions }] };
      }
      try {
        const latest = await getResume(user.id, state.resumeId);
        const proposedVersion = String(state.pendingEdit.resume.updated_at || "");
        const latestVersion = String(latest.updated_at || "");
        if (proposedVersion && latestVersion && proposedVersion !== latestVersion) {
          return {
            state: { ...state, step: "awaiting_edit_instruction", pendingEdit: undefined },
            messages: [{ text: "Your resume changed after this proposal was prepared, so I did not overwrite newer information. Please describe the edit again and I will create a fresh proposal." }],
          };
        }
        const saved = await updateResume(user.id, state.resumeId, state.pendingEdit.resume);
        return {
          state: { ...state, step: "reviewing", pendingEdit: undefined, resumeTitle: String(saved.title || state.resumeTitle) },
          messages: [{ text: "Your approved changes have been saved. You can keep editing, or generate final wording again before downloading the updated PDF.", options: reviewOptions }],
        };
      } catch (error) {
        return { state, messages: [{ text: `I could not save the approved changes: ${(error as Error).message}. Your proposal is still waiting for confirmation.`, options: editConfirmationOptions }] };
      }
    }
    if (["cancel_edit", "cancel", "no", "discard"].includes(command)) {
      return { state: { ...state, step: "reviewing", pendingEdit: undefined }, messages: [{ text: "The proposal was discarded. Your resume was not changed.", options: reviewOptions }] };
    }
    if (["revise_edit", "revise", "change"].includes(command)) {
      return { state: { ...state, step: "awaiting_edit_instruction", pendingEdit: undefined }, messages: [{ text: "What would you like to change? For example: “Make my summary shorter and focus it on a Data Analyst role.”" }] };
    }
    return { state, messages: [{ text: "Please choose Apply changes, Revise request, or Cancel. Nothing will be saved until you choose Apply changes or type OK.", options: editConfirmationOptions }] };
  }

  if ((state.step === "reviewing" || state.step === "completed") && (command === "edit_resume" || command === "edit")) {
    return { state: { ...state, step: "awaiting_edit_instruction" }, messages: [{ text: "Describe what you want to change. I will analyze the request and show a proposal before changing your resume." }] };
  }

  if ((state.step === "reviewing" || state.step === "completed") && (command === "choose_template" || command === "choose template" || command === "template" || command === "templates")) {
    const templates = await listResumeTemplates();
    const templateOptions: ChatOption[] = templates.map((template) => ({
      label: template.name,
      value: `template:${template.id}`,
      description: template.description || "Apply this template to the preview and final PDF.",
    }));
    return {
      state: { ...state, step: "awaiting_template" },
      messages: [{ text: "Choose a resume template for your preview and final PDF:", options: templateOptions }],
    };
  }

  if (state.step === "reviewing" && (value === "enrich_ats" || command === "enrich" || command.includes("enrich"))) {
    return {
      state: { ...state, step: "awaiting_enrichment_choice" },
      messages: [enrichmentChoiceMessage(state.draft || {})],
    };
  }

  if (state.step === "reviewing" && (command === "generate_resume" || command === "generate")) {
    return generateVerifiedResume(state, user);
  }

  if (state.step === "awaiting_template") {
    const templateChoice = value.startsWith("template:") ? value.slice("template:".length) : "";
    if (!templateChoice || !state.resumeId) {
      return { state, messages: [{ text: "Please choose one of the available resume templates." }] };
    }
    try {
      await selectResumeTemplate(user.id, state.resumeId, templateChoice);
      return {
        state: { ...state, step: "completed", templateChoice },
        messages: [{ text: "Template applied to your resume and final PDF. Your resume is ready to download.", options: [{ label: "Open download panel", value: "open_resume_dashboard", description: "Open the Resume Builder panel to download the selected-template PDF." }, ...editOptions] }],
      };
    } catch (error) {
      return { state, messages: [{ text: `I could not apply that template: ${(error as Error).message}. Please choose a template again.` }] };
    }
  }

  if (state.step === "reviewing" || state.step === "completed" || state.step === "awaiting_edit_instruction") {
    if (!state.resumeId) {
      return { state, messages: [{ text: "There is no saved resume to edit yet. Create or upload a resume first." }] };
    }
    if (!clean(value)) {
      return { state, messages: [{ text: "Describe the change you would like to make." }] };
    }
    try {
      const currentResume = await getResume(user.id, state.resumeId);
      const proposal = await suggestResumeEdit(user.id, currentResume, clean(value));
      return {
        state: { ...state, step: "awaiting_edit_confirmation", pendingEdit: proposal },
        messages: [{ text: formatEditProposal(proposal), options: editConfirmationOptions }],
      };
    } catch (error) {
      return { state: { ...state, step: "reviewing" }, messages: [{ text: `I could not prepare a safe edit proposal: ${(error as Error).message}. Your resume was not changed.`, options: reviewOptions }] };
    }
  }
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
  if (state.step === "awaiting_location") return { state: updateDraft(state, { location: isSkip(value) ? "" : normalizeLocation(value) }, "awaiting_role"), messages: [{ text: "What role are you targeting? For example: Data Analyst or Frontend Developer." }] };
  if (state.step === "awaiting_role") {
    if (clean(value).length < 2) return { state, messages: [{ text: "Please enter the role you are targeting." }] };
    return { state: updateDraft(state, { targetRole: clean(value).replace(/^role\s*:\s*/i, "") }, "awaiting_summary"), messages: [{ text: "Write a short summary, share a few facts, or type Skip. You can improve it later with AI.", options: skipOption }] };
  }
  if (state.step === "awaiting_summary") {
    if (isSkip(value) || (clean(value).length >= 3 && clean(value).length < 30)) {
      return { state: updateDraft(state, { summary: isSkip(value) ? "" : clean(value) }, "awaiting_skills"), messages: [{ text: "List your key skills, separated by commas. For example: Python, SQL, Power BI, Excel." }] };
    }
    if (clean(value).length < 30) return { state, messages: [{ text: "Please add a little more detail—at least 30 characters makes your summary useful to recruiters." }] };
    return { state: updateDraft(state, { summary: clean(value) }, "awaiting_skills"), messages: [{ text: "List your key skills, separated by commas. For example: Python, SQL, Power BI, Excel." }] };
  }
  if (state.step === "awaiting_skills") {
    const rawSkills = clean(value).split(",").map(clean).filter(Boolean);
    if (!rawSkills.length) return { state, messages: [{ text: "Please add at least one skill, separated by commas." }] };
    const mergedSkills = [...new Set([...(state.draft?.skills || []), ...rawSkills])].slice(0, 25);
    if ((state.draft?.projects?.length || 0) > 0 || (state.draft?.education?.length || 0) > 0) {
      const next = updateDraft(state, { skills: mergedSkills }, "confirming");
      return { state: next, messages: [{ text: `Updated skills: ${mergedSkills.join(", ")}.` }, reviewMessage(next.draft || {})] };
    }
    return { state: updateDraft(state, { skills: mergedSkills }, "awaiting_experience"), messages: [{ text: EXPERIENCE_PROMPT_TEXT, options: skipOption }] };
  }
  if (state.step === "awaiting_experience") {
    if (isSkip(value)) return { state: updateDraft(state, {}, "awaiting_education"), messages: [{ text: draftFieldPrompt("education"), options: skipOption }] };
    const experience = parseExperienceInput(value);
    if (!experience.length) {
      return {
        state,
        messages: [{
          text: `Please enter your experience with at least a company and role, or type Skip.\n\nExample:\nCompany: Acme Technologies\nRole: Data Analyst\nDuration: Jan 2024 – Present\n\nResponsibilities:\n• Developed Power BI dashboards for business reporting.\n• Analyzed data using SQL and Excel.\n• Automated recurring reports and generated business insights.`,
          options: skipOption,
        }],
      };
    }
    const updated = [...(state.draft?.experience || []), ...experience];
    const total = updated.length;
    const addedSummary = experience.map((e) => `${e.company} (${e.role})`).join(", ");
    return {
      state: updateDraft(state, { experience: updated }, "awaiting_experience_more"),
      messages: [{
        text: `Added experience: ${addedSummary} (Total: ${total} ${total === 1 ? "entry" : "entries"}).\n\nWould you like to add another experience, or go to the next section?`,
        options: [
          { label: "+ Add another experience", value: "add_another_experience", description: "Add another past position or internship." },
          { label: "Go to Education →", value: "next_section", description: "Continue to your education details." },
        ],
      }],
    };
  }
  if (state.step === "awaiting_experience_more") {
    if (command === "add_another_experience" || ["add", "another", "yes"].includes(command) || command.includes("add experience") || command.includes("another experience") || command.includes("add another")) {
      return {
        state: { ...state, step: "awaiting_experience" },
        messages: [{
          text: `Add another experience:\n\nExample:\nCompany: Acme Technologies\nRole: Data Analyst\nDuration: Jan 2024 – Present\n\nResponsibilities:\n• Developed Power BI dashboards for business reporting.\n• Analyzed data using SQL and Excel.\n\nType Skip / Next to move to Education.`,
          options: [{ label: "Go to Education →", value: "next_section" }, ...skipOption],
        }],
      };
    }
    if (command === "next_section" || ["next", "skip", "continue", "done", "no", "proceed", "go to next", "next section"].includes(command) || command.includes("next section") || command.includes("go to next") || command.includes("education")) {
      if ((state.draft?.projects?.length || 0) > 0) {
        const next = updateDraft(state, {}, "confirming");
        return { state: next, messages: [reviewMessage(next.draft || {})] };
      }
      return { state: updateDraft(state, {}, "awaiting_education"), messages: [{ text: draftFieldPrompt("education"), options: skipOption }] };
    }
    const experience = parseExperienceInput(value);
    if (experience.length) {
      const updated = [...(state.draft?.experience || []), ...experience];
      const total = updated.length;
      const addedSummary = experience.map((e) => `${e.company} (${e.role})`).join(", ");
      return {
        state: updateDraft(state, { experience: updated }, "awaiting_experience_more"),
        messages: [{
          text: `Added experience: ${addedSummary} (Total: ${total} ${total === 1 ? "entry" : "entries"}).\n\nWould you like to add another experience, or go to the next section?`,
          options: [
            { label: "+ Add another experience", value: "add_another_experience", description: "Add another past position or internship." },
            { label: "Go to Education →", value: "next_section", description: "Continue to your education details." },
          ],
        }],
      };
    }
    return {
      state,
      messages: [{
        text: "Please choose '+ Add another experience' to add another entry, or 'Go to Education →' to proceed.",
        options: [
          { label: "+ Add another experience", value: "add_another_experience" },
          { label: "Go to Education →", value: "next_section" },
        ],
      }],
    };
  }
  if (state.step === "awaiting_education") {
    if (isSkip(value)) {
      if (state.pendingField === "education.ug") {
        return { state, messages: [{ text: "UG education is required for a fresher resume. Please add at least your degree and college. Your other resume details are still saved.", options: skipOption }] };
      }
      return { state: updateDraft(state, {}, "awaiting_project"), messages: [{ text: "Add one relevant project in this format: Project title | What you built and its outcome. Short details such as 'sales dashboard power bi' are also welcome. Type Skip to omit it.", options: skipOption }] };
    }
    const education = parseEducationInput(value);
    if (!Array.isArray(education)) return { state, messages: [{ text: education.error, options: skipOption }] };
    const mergedEducation = mergeEducation(state.draft?.education, education);
    if (state.pendingField === "education.ug") {
      const next = updateDraft({ ...state, pendingField: undefined }, { education: mergedEducation }, "confirming");
      return { state: next, messages: [reviewMessage(next.draft || {})] };
    }
    const total = mergedEducation.length;
    const addedSummary = education.map((e) => `${e.degree || e.level} at ${e.school}`).join(", ");
    return {
      state: updateDraft(state, { education: mergedEducation }, "awaiting_education_more"),
      messages: [{
        text: `Added education: ${addedSummary} (Total: ${total} ${total === 1 ? "entry" : "entries"}).\n\nWould you like to add another education entry (e.g. UG, PG, or Diploma), or go to the next section?`,
        options: [
          { label: "+ Add another education", value: "add_another_education", description: "Add another degree, diploma, or qualification." },
          { label: "Go to Projects →", value: "next_section", description: "Continue to your projects." },
        ],
      }],
    };
  }
  if (state.step === "awaiting_education_more") {
    if (command === "add_another_education" || ["add", "another", "yes"].includes(command) || command.includes("add education") || command.includes("another education") || command.includes("add another")) {
      return {
        state: { ...state, step: "awaiting_education" },
        messages: [{
          text: "Add another education entry in a short format, for example: UG: BCA, Nandha College, 2019-2022, CGPA: 7.8. Or type Next to continue.",
          options: [{ label: "Go to Projects →", value: "next_section" }, ...skipOption],
        }],
      };
    }
    if (command === "next_section" || ["next", "skip", "continue", "done", "no", "proceed", "go to next", "next section"].includes(command) || command.includes("next section") || command.includes("go to next") || command.includes("project")) {
      if ((state.draft?.projects?.length || 0) > 0) {
        const next = updateDraft(state, {}, "confirming");
        return { state: next, messages: [reviewMessage(next.draft || {})] };
      }
      return { state: updateDraft(state, {}, "awaiting_project"), messages: [{ text: "Add one relevant project in this format: Project title | What you built and its outcome. Short details such as 'sales dashboard power bi' are also welcome. Type Skip to omit it.", options: skipOption }] };
    }
    const parsed = parseEducationInput(value);
    if (Array.isArray(parsed) && parsed.length) {
      const mergedEducation = mergeEducation(state.draft?.education, parsed);
      const total = mergedEducation.length;
      const addedSummary = parsed.map((e) => `${e.degree || e.level} at ${e.school}`).join(", ");
      return {
        state: updateDraft(state, { education: mergedEducation }, "awaiting_education_more"),
        messages: [{
          text: `Added education: ${addedSummary} (Total: ${total} ${total === 1 ? "entry" : "entries"}).\n\nWould you like to add another education entry, or go to the next section?`,
          options: [
            { label: "+ Add another education", value: "add_another_education" },
            { label: "Go to Projects →", value: "next_section" },
          ],
        }],
      };
    }
    return {
      state,
      messages: [{
        text: "Please choose '+ Add another education' to add another entry, or 'Go to Projects →' to proceed.",
        options: [
          { label: "+ Add another education", value: "add_another_education" },
          { label: "Go to Projects →", value: "next_section" },
        ],
      }],
    };
  }
  if (state.step === "awaiting_project") {
    if (isSkip(value)) return { state: updateDraft(state, {}, "awaiting_linkedin"), messages: [{ text: "Please provide your LinkedIn profile URL, or type Skip.", options: skipOption }] };
    const projects = clean(value).split(/\s*;\s*/).filter(Boolean).map((raw) => {
      const projectFields = splitFields(raw, 2);
      if (projectFields) return { title: projectFields[0], description: projectFields.slice(1).join(" | ") };
      return raw.length >= 3
        ? { title: raw.split(/\s+(?:using|with)\s+/i)[0].replace(/\b\w/g, (letter) => letter.toUpperCase()), description: raw }
        : undefined;
    }).filter((project): project is { title: string; description: string } => Boolean(project));
    if (!projects.length) return { state, messages: [{ text: "Please add a project detail or choose Skip.", options: skipOption }] };
    const updated = [...(state.draft?.projects || []), ...projects];
    const total = updated.length;
    const addedSummary = projects.map((p) => p.title).join(", ");
    return {
      state: updateDraft(state, { projects: updated }, "awaiting_project_more"),
      messages: [{
        text: `Added project: ${addedSummary} (Total: ${total} ${total === 1 ? "project" : "projects"}).\n\nWould you like to add another project, or go to the next section?`,
        options: [
          { label: "+ Add another project", value: "add_another_project", description: "Add another personal, academic, or work project." },
          { label: "Go to next section (Links)", value: "next_section", description: "Continue to your professional links." },
        ],
      }],
    };
  }
  if (state.step === "awaiting_project_more") {
    if (command === "add_another_project" || ["add", "another", "yes"].includes(command) || command.includes("add project") || command.includes("another project") || command.includes("add another")) {
      return {
        state: { ...state, step: "awaiting_project" },
        messages: [{
          text: "Add another project in this format: Project title | What you built and its outcome. Short details are also welcome.",
          options: [{ label: "Go to next section (Links)", value: "next_section" }, ...skipOption],
        }],
      };
    }
    if (command === "next_section" || ["next", "skip", "continue", "done", "no", "proceed", "go to next", "next section"].includes(command) || command.includes("next section") || command.includes("go to next") || command.includes("link")) {
      if ((state.draft?.links?.length || 0) > 0 || (state.draft?.certifications?.length || 0) > 0) {
        const next = updateDraft(state, {}, "confirming");
        return { state: next, messages: [reviewMessage(next.draft || {})] };
      }
      return { state: updateDraft(state, {}, "awaiting_linkedin"), messages: [{ text: "Please provide your LinkedIn profile URL, or type Skip.", options: skipOption }] };
    }
    const projects = clean(value).split(/\s*;\s*/).filter(Boolean).map((raw) => {
      const projectFields = splitFields(raw, 2);
      if (projectFields) return { title: projectFields[0], description: projectFields.slice(1).join(" | ") };
      return raw.length >= 3
        ? { title: raw.split(/\s+(?:using|with)\s+/i)[0].replace(/\b\w/g, (letter) => letter.toUpperCase()), description: raw }
        : undefined;
    }).filter((project): project is { title: string; description: string } => Boolean(project));
    if (projects.length) {
      const updated = [...(state.draft?.projects || []), ...projects];
      const total = updated.length;
      const addedSummary = projects.map((p) => p.title).join(", ");
      return {
        state: updateDraft(state, { projects: updated }, "awaiting_project_more"),
        messages: [{
          text: `Added project: ${addedSummary} (Total: ${total} ${total === 1 ? "project" : "projects"}).\n\nWould you like to add another project, or go to the next section?`,
          options: [
            { label: "+ Add another project", value: "add_another_project", description: "Add another personal, academic, or work project." },
            { label: "Go to next section (Links)", value: "next_section", description: "Continue to your professional links." },
          ],
        }],
      };
    }
    return {
      state,
      messages: [{
        text: "Please choose '+ Add another project' to add another project, or 'Go to next section (Links)' to proceed.",
        options: [
          { label: "+ Add another project", value: "add_another_project" },
          { label: "Go to next section (Links)", value: "next_section" },
        ],
      }],
    };
  }
  if (state.step === "awaiting_linkedin") {
    const normalized = optionalProfileUrl(value);
    if (normalized.error) return { state, messages: [{ text: normalized.error, options: skipOption }] };
    const links = state.draft?.links || [];
    const nextLinks = !normalized.value ? links : [...links.filter((link) => !/^LinkedIn\s*:/i.test(link)), `LinkedIn: ${normalized.value}`];
    return { state: updateDraft(state, { links: nextLinks }, "awaiting_github"), messages: [{ text: "Please provide your GitHub profile URL, or type Skip.", options: skipOption }] };
  }
  if (state.step === "awaiting_github") {
    const normalized = optionalProfileUrl(value);
    if (normalized.error) return { state, messages: [{ text: normalized.error, options: skipOption }] };
    const links = state.draft?.links || [];
    const nextLinks = !normalized.value ? links : [...links.filter((link) => !/^GitHub\s*:/i.test(link)), `GitHub: ${normalized.value}`];
    return { state: updateDraft(state, { links: nextLinks }, "awaiting_portfolio"), messages: [{ text: "Please provide your portfolio or personal website URL, or type Skip.", options: skipOption }] };
  }
  if (state.step === "awaiting_portfolio") {
    const normalized = optionalProfileUrl(value);
    if (normalized.error) return { state, messages: [{ text: normalized.error, options: skipOption }] };
    const links = state.draft?.links || [];
    const nextLinks = !normalized.value ? links : [...links.filter((link) => !/^(Portfolio|Website)\s*:/i.test(link)), `Portfolio: ${normalized.value}`];
    return { state: updateDraft(state, { links: nextLinks }, "awaiting_certifications"), messages: [{ text: "Do you have any certifications you'd like to add? Enter one per line, for example: Microsoft Power BI Data Analyst Associate - Microsoft - 2025. Type Skip if you do not have any.", options: skipOption }] };
  }
  if (state.step === "awaiting_certifications") {
    if (isSkip(value)) return { state: updateDraft(state, {}, "awaiting_achievements"), messages: [{ text: "Do you have any achievements, awards, honors, or recognitions you'd like to add? Enter one per line, or type Skip.", options: skipOption }] };
    const certifications = parseCertificationInput(value);
    if (!certifications.length) return { state, messages: [{ text: "Add at least a certification name, or type Skip.", options: skipOption }] };
    const updated = [...(state.draft?.certifications || []), ...certifications];
    const total = updated.length;
    const addedSummary = certifications.map((c) => c.name).join(", ");
    return {
      state: updateDraft(state, { certifications: updated }, "awaiting_certifications_more"),
      messages: [{
        text: `Added certification: ${addedSummary} (Total: ${total} ${total === 1 ? "entry" : "entries"}).\n\nWould you like to add another certification, or go to the next section?`,
        options: [
          { label: "+ Add another certification", value: "add_another_certification", description: "Add another certification or license." },
          { label: "Go to Achievements →", value: "next_section", description: "Continue to achievements and awards." },
        ],
      }],
    };
  }
  if (state.step === "awaiting_certifications_more") {
    if (command === "add_another_certification" || ["add", "another", "yes"].includes(command) || command.includes("add certification") || command.includes("another cert") || command.includes("add another")) {
      return {
        state: { ...state, step: "awaiting_certifications" },
        messages: [{
          text: "Add another certification: Certificate Name - Issuing Organization - Year. Or type Next to continue.",
          options: [{ label: "Go to Achievements →", value: "next_section" }, ...skipOption],
        }],
      };
    }
    if (command === "next_section" || ["next", "skip", "continue", "done", "no", "proceed", "go to next", "next section"].includes(command) || command.includes("next section") || command.includes("go to next") || command.includes("achievement")) {
      if ((state.draft?.achievements?.length || 0) > 0) {
        const next = updateDraft(state, {}, "confirming");
        return { state: next, messages: [reviewMessage(next.draft || {})] };
      }
      return { state: updateDraft(state, {}, "awaiting_achievements"), messages: [{ text: "Do you have any achievements, awards, honors, or recognitions you'd like to add? Enter one per line, or type Skip.", options: skipOption }] };
    }
    const certs = parseCertificationInput(value);
    if (certs.length) {
      const updated = [...(state.draft?.certifications || []), ...certs];
      const total = updated.length;
      const addedSummary = certs.map((c) => c.name).join(", ");
      return {
        state: updateDraft(state, { certifications: updated }, "awaiting_certifications_more"),
        messages: [{
          text: `Added certification: ${addedSummary} (Total: ${total} ${total === 1 ? "entry" : "entries"}).\n\nWould you like to add another certification, or go to the next section?`,
          options: [
            { label: "+ Add another certification", value: "add_another_certification" },
            { label: "Go to Achievements →", value: "next_section" },
          ],
        }],
      };
    }
    return {
      state,
      messages: [{
        text: "Please choose '+ Add another certification' or 'Go to Achievements →' to proceed.",
        options: [
          { label: "+ Add another certification", value: "add_another_certification" },
          { label: "Go to Achievements →", value: "next_section" },
        ],
      }],
    };
  }
  if (state.step === "awaiting_achievements") {
    if (isSkip(value)) {
      const next = updateDraft(state, {}, "confirming");
      return { state: next, messages: [reviewMessage(next.draft || {})] };
    }
    const achievements = parseAchievementInput(value);
    if (!achievements.length) return { state, messages: [{ text: "Add at least an achievement title, or type Skip.", options: skipOption }] };
    const updated = [...(state.draft?.achievements || []), ...achievements];
    const total = updated.length;
    const addedSummary = achievements.map((a) => a.title).join(", ");
    return {
      state: updateDraft(state, { achievements: updated }, "awaiting_achievements_more"),
      messages: [{
        text: `Added achievement: ${addedSummary} (Total: ${total} ${total === 1 ? "entry" : "entries"}).\n\nWould you like to add another achievement, or proceed to review?`,
        options: [
          { label: "+ Add another achievement", value: "add_another_achievement", description: "Add another award, competition, or recognition." },
          { label: "Go to Review →", value: "next_section", description: "Review all details and check ATS readiness." },
        ],
      }],
    };
  }
  if (state.step === "awaiting_achievements_more") {
    if (command === "add_another_achievement" || ["add", "another", "yes"].includes(command) || command.includes("add achievement") || command.includes("another achieve") || command.includes("add another")) {
      return {
        state: { ...state, step: "awaiting_achievements" },
        messages: [{
          text: "Add another achievement: Title | Description | Year. Or type Next to review.",
          options: [{ label: "Go to Review →", value: "next_section" }, ...skipOption],
        }],
      };
    }
    if (command === "next_section" || ["next", "skip", "continue", "done", "no", "proceed", "go to next", "next section"].includes(command) || command.includes("next section") || command.includes("go to next") || command.includes("review")) {
      const next = updateDraft(state, {}, "confirming");
      return { state: next, messages: [reviewMessage(next.draft || {})] };
    }
    const achs = parseAchievementInput(value);
    if (achs.length) {
      const updated = [...(state.draft?.achievements || []), ...achs];
      const total = updated.length;
      const addedSummary = achs.map((a) => a.title).join(", ");
      return {
        state: updateDraft(state, { achievements: updated }, "awaiting_achievements_more"),
        messages: [{
          text: `Added achievement: ${addedSummary} (Total: ${total} ${total === 1 ? "entry" : "entries"}).\n\nWould you like to add another achievement, or proceed to review?`,
          options: [
            { label: "+ Add another achievement", value: "add_another_achievement" },
            { label: "Go to Review →", value: "next_section" },
          ],
        }],
      };
    }
    return {
      state,
      messages: [{
        text: "Please choose '+ Add another achievement' or 'Go to Review →' to proceed.",
        options: [
          { label: "+ Add another achievement", value: "add_another_achievement" },
          { label: "Go to Review →", value: "next_section" },
        ],
      }],
    };
  }
  if (state.step === "awaiting_upload_role") {
    if (clean(value).length < 2) return { state, messages: [{ text: "Please enter the role you are targeting." }] };
    const targetRole = clean(value).replace(/^role\s*:\s*/i, "");
    if (state.pendingUploadFile) {
      const file = state.pendingUploadFile;
      const nextState = { ...state, pendingUploadFile: undefined, draft: { ...state.draft, targetRole } };
      return processUploadedResume(nextState, user, file, targetRole);
    }
    return { state: updateDraft(state, { targetRole }, "awaiting_upload_job_description"), messages: [{ text: "Paste the job description for that role, if you have it. This lets the ATS analysis compare your resume to the role. Type Skip if you do not have one yet.", options: skipOption }] };
  }
  if (state.step === "awaiting_upload_job_description") {
    return { state: updateDraft(state, { jobDescription: isSkip(value) ? "" : clean(value) }, "awaiting_experience_level"), messages: [{ text: "Finally, choose your career level so I can apply the right one-page or two-page structure.", options: [{ label: "Fresher / student", value: "fresher", description: "One-page structure prioritizing skills, education, and projects." }, { label: "Experienced professional", value: "experienced", description: "Up-to-two-page structure prioritizing measurable work impact." }] }] };
  }
  if (state.step === "awaiting_import_linkedin") {
    return saveImportedProfessionalLink(state, user, "LinkedIn", value, "awaiting_import_github", "Please provide your GitHub profile URL, or type Skip.");
  }
  if (state.step === "awaiting_import_github") {
    return saveImportedProfessionalLink(state, user, "GitHub", value, "awaiting_import_portfolio", "Please provide your portfolio or personal website URL, or type Skip.");
  }
  if (state.step === "awaiting_import_portfolio") {
    const result = await saveImportedProfessionalLink(state, user, "Portfolio", value, "reviewing", "");
    if (result.state.step !== "reviewing") return result;
    return {
      ...result,
      messages: [{ text: "Your imported details and professional links are saved for review. Edit any extracted information first; when it is correct, choose Generate final wording for the complete target-role-focused resume.", options: reviewOptions }],
    };
  }
  if (state.step === "confirming") {
    if (
      value === "create_now" ||
      command === "create" ||
      command === "create now" ||
      command === "create my resume" ||
      command === "create resume" ||
      command === "yes" ||
      command === "proceed" ||
      command === "confirm" ||
      command === "generate" ||
      command === "save"
    ) {
      return createFromDraft(state, user);
    }
    if (
      value === "enrich_ats" ||
      command === "enrich" ||
      command === "enrich ats" ||
      command === "enrich for high ats" ||
      command.includes("enrich") ||
      command.includes("improve") ||
      command.includes("boost")
    ) {
      return {
        state: { ...state, step: "awaiting_enrichment_choice" },
        messages: [enrichmentChoiceMessage(state.draft || {})],
      };
    }
    return {
      state,
      messages: [
        {
          text: "Please choose 'Create my resume now' to proceed, or '⚡ Enrich for High ATS' to add more details.",
          options: reviewMessage(state.draft || {}).options,
        },
      ],
    };
  }
  if (state.step === "awaiting_enrichment_choice") {
    if (
      value === "create_now" ||
      command === "create" ||
      command === "create now" ||
      command === "create my resume" ||
      command === "create resume" ||
      command === "yes" ||
      command === "proceed"
    ) {
      return createFromDraft(state, user);
    }
    if (value === "back_to_review" || command === "back" || command === "review") {
      return { state: { ...state, step: "confirming" }, messages: [reviewMessage(state.draft || {})] };
    }
    if (value === "enrich_project" || command.includes("project")) {
      return {
        state: { ...state, step: "awaiting_project" },
        messages: [{
          text: "Add another project in this format: Project title | What you built and its outcome. Adding 2+ projects significantly improves your ATS score.",
          options: [{ label: "Back to Review", value: "back_to_review" }, ...skipOption],
        }],
      };
    }
    if (value === "enrich_skills" || command.includes("skill")) {
      return {
        state: { ...state, step: "awaiting_skills" },
        messages: [{
          text: `Current skills: ${(state.draft?.skills || []).join(", ") || "None"}.\n\nList additional skills or tools separated by commas to strengthen your ATS keyword match:`,
          options: [{ label: "Back to Review", value: "back_to_review" }, ...skipOption],
        }],
      };
    }
    if (value === "enrich_links" || command.includes("link") || command.includes("linkedin") || command.includes("github") || command.includes("portfolio")) {
      return {
        state: { ...state, step: "awaiting_linkedin" },
        messages: [{
          text: "Add your LinkedIn profile URL (or type Skip):",
          options: [{ label: "Back to Review", value: "back_to_review" }, ...skipOption],
        }],
      };
    }
    if (value === "enrich_certifications" || command.includes("cert")) {
      return {
        state: { ...state, step: "awaiting_certifications" },
        messages: [{
          text: "Add certifications one per line (Certificate Name - Organization - Year). Or type Skip:",
          options: [{ label: "Back to Review", value: "back_to_review" }, ...skipOption],
        }],
      };
    }
    if (value === "enrich_achievements" || command.includes("achieve") || command.includes("award")) {
      return {
        state: { ...state, step: "awaiting_achievements" },
        messages: [{
          text: "Add achievements or awards one per line. Or type Skip:",
          options: [{ label: "Back to Review", value: "back_to_review" }, ...skipOption],
        }],
      };
    }
    if (value === "enrich_experience" || command.includes("experience") || command.includes("job")) {
      return {
        state: { ...state, step: "awaiting_experience" },
        messages: [{
          text: `Add your experience:\n\nExample:\nCompany: Acme Technologies\nRole: Data Analyst\nDuration: Jan 2024 – Present\n\nResponsibilities:\n• Developed Power BI dashboards for business reporting.\n• Analyzed data using SQL and Excel.`,
          options: [{ label: "Back to Review", value: "back_to_review" }, ...skipOption],
        }],
      };
    }
    if (value === "enrich_summary" || command.includes("summary")) {
      return {
        state: { ...state, step: "awaiting_summary" },
        messages: [{
          text: "Write a 2–4 sentence professional summary highlighting your top skills and career target:",
          options: [{ label: "Back to Review", value: "back_to_review" }, ...skipOption],
        }],
      };
    }
    return {
      state,
      messages: [enrichmentChoiceMessage(state.draft || {})],
    };
  }
  return { state, messages: [{ text: "Choose Create a resume or Upload an existing resume to continue.", options: choices }] };
}

export async function processUploadedResume(
  state: ResumeBuilderFlowState,
  user: User,
  file: File,
  targetRole: string,
): Promise<ResumeBuilderFlowResult> {
  const experienceLevel = state.draft?.experienceLevel || "fresher";
  const jobDescription = state.draft?.jobDescription || "";
  try {
    const analysis = await analyzeResumeUpload(user.id, file, targetRole, jobDescription);
    const initialAts = analysis.atsAnalysis as Record<string, unknown> | undefined;

    const resume = await createImportDraft(
      user.id,
      file.name,
      analysis.parsedResume,
      initialAts ?? {},
      targetRole,
      experienceLevel,
    );
    const id = Number(resume.id);

    let savedResume: Record<string, unknown> = resume;
    let roleAnalysis: { matched_skills?: string[]; recommended_skills_to_learn?: string[]; missing_information?: string[] } | undefined;
    let freshAnalysis: Record<string, unknown> | undefined = initialAts;
    let finalScore = Number(
      (initialAts?.normalizedScore ?? (initialAts?.score as { normalized_score?: number })?.normalized_score) || 0,
    );

    try {
      const generated = await generateImportedResume(user.id, resume, targetRole, jobDescription);
      if (generated?.resume) {
        savedResume = await updateResume(user.id, id, generated.resume);
        roleAnalysis = generated.role_analysis;
      }
      const reanalysis = await analyzeSavedResume(user.id, id, jobDescription, targetRole);
      freshAnalysis = reanalysis as Record<string, unknown>;
      const scoreNum = Number((reanalysis.score as { normalized_score?: number })?.normalized_score);
      if (Number.isFinite(scoreNum)) finalScore = scoreNum;
    } catch {
      // If AI generation has a temporary provider timeout, keep the clean imported draft and initial ATS analysis.
    }

    const title = String(savedResume.title || targetRole || file.name);
    const scorecardMessage = buildAtsScorecardMessage(
      file.name,
      targetRole,
      finalScore,
      freshAnalysis,
      roleAnalysis,
      Boolean(roleAnalysis || freshAnalysis !== initialAts),
    );

    return {
      state: {
        ...state,
        step: "reviewing",
        resumeId: id,
        resumeTitle: title,
        atsScore: Number.isFinite(finalScore) ? finalScore : undefined,
        draft: {
          ...state.draft,
          targetRole,
          experienceLevel,
          title,
        },
      },
      messages: [scorecardMessage],
    };
  } catch (error) {
    const rawError = (error as Error).message || "";
    const isSchoolError = /missing required field.*school/i.test(rawError);
    const isBulletsError = /ai_generated_bullets|must contain at most|at most 20/i.test(rawError);
    const userFriendlyMessage = isSchoolError
      ? "I couldn’t find education information in the uploaded resume. You can add or edit your education anytime in the resume editor."
      : isBulletsError
      ? "I analyzed your resume, but some extracted experience details needed cleanup. Please try uploading your resume again, or click 'Create a resume' to edit step-by-step."
      : `I couldn’t analyze that file: ${rawError}. Please try uploading another PDF, DOC, DOCX, or TXT file.`;

    return {
      state: {
        ...state,
        step: "error",
        error: rawError,
        draft: {
          ...state.draft,
          targetRole,
          jobDescription,
          experienceLevel,
        },
      },
      messages: [{
        text: userFriendlyMessage,
        options: [
          { label: "Try again", value: "retry_upload", description: "Attach another resume file." },
          { label: "Create a resume", value: "create_resume", description: "Create your resume step-by-step." },
        ],
      }],
    };
  }
}

export async function importResumeBuilderFile(state: ResumeBuilderFlowState, user: User, file: File): Promise<ResumeBuilderFlowResult> {
  const targetRole = state.draft?.targetRole?.trim() || "";
  if (!targetRole) {
    return {
      state: {
        ...state,
        step: "awaiting_upload_role",
        pendingUploadFile: file,
      },
      messages: [{
        text: `I've received your resume (**${file.name}**).\n\nTo tailor your resume with AI and calculate your ATS match score accurately, **what role are you targeting?** (e.g. Data Analyst, Python Developer, Frontend Developer, Full Stack Developer)`,
      }],
    };
  }
  return processUploadedResume(state, user, file, targetRole);
}

