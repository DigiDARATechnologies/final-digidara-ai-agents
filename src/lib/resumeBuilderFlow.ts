import type { ChatOption, User } from "../types";
import {
  analyzeResumeUpload,
  createImportDraft,
  createResume,
  ensureResumeProfile,
  fetchResumeFacts,
  generateImportedResume,
  analyzeSavedResume,
  getResume,
  listResumeTemplates,
  selectResumeTemplate,
  suggestResumeEdit,
  resumeChatTurn,
  suggestResumeWording,
  type WordingField,
  updateResume,
  type ResumeEditProposal,
  type ResumeCreateInput,
  type ResumeFacts,
} from "./resumeBuilderApi";
import { parseLinkedInExport } from "./linkedinExport";
import { displayRole, learnerGoal } from "./learnerContext";

export type ResumeBuilderStep = "choose_workflow" | "awaiting_experience_level" | "awaiting_title" | "awaiting_name" | "awaiting_email" | "awaiting_phone" | "awaiting_location" | "awaiting_role" | "awaiting_summary" | "awaiting_skills" | "awaiting_experience" | "awaiting_experience_more" | "awaiting_education" | "awaiting_education_more" | "awaiting_project" | "awaiting_project_more" | "awaiting_linkedin" | "awaiting_github" | "awaiting_portfolio" | "awaiting_certifications" | "awaiting_certifications_more" | "awaiting_achievements" | "awaiting_achievements_more" | "confirming" | "awaiting_enrichment_choice" | "awaiting_upload_role" | "awaiting_upload_job_description" | "awaiting_upload" | "awaiting_paste_text" | "awaiting_import_zip" | "awaiting_import_linkedin" | "awaiting_import_github" | "awaiting_import_portfolio" | "reviewing" | "awaiting_edit_instruction" | "awaiting_edit_confirmation" | "awaiting_template" | "completed" | "error";
interface ResumeDraft {
  title?: string; name?: string; email?: string; phone?: string; location?: string; targetRole?: string; jobDescription?: string; experienceLevel?: "fresher" | "experienced"; summary?: string;
  skills?: string[]; experience?: ResumeCreateInput["experience"]; education?: ResumeCreateInput["education"]; projects?: ResumeCreateInput["projects"]; certifications?: NonNullable<ResumeCreateInput["certifications"]>; achievements?: NonNullable<ResumeCreateInput["achievements"]>; links?: string[];
  skipEducation?: boolean;
}
export interface ResumeBuilderFlowState { step: ResumeBuilderStep; draft?: ResumeDraft; resumeId?: number; resumeTitle?: string; atsScore?: number; templateChoice?: string; pendingField?: "education.ug"; pendingEdit?: ResumeEditProposal; pendingUploadFile?: File; error?: string;
  /** The recent conversation, sent with every AI chat turn so "change that" or
   * "the second one" can be resolved. */
  history?: ResumeChatTurnHistory;
  /** The last message shown (with its buttons), so a jump to edit one field
   * can come back to exactly this question. */
  lastMessage?: ResumeBuilderMessage;
  /** Set by "change my <field>": where the chat was, to return to once that
   * one field is saved -- instead of re-asking every question after it. */
  returnTo?: { step: ResumeBuilderStep; message?: ResumeBuilderMessage };
  /** A stronger wording offered for what the candidate just wrote, waiting
   * for "Use this", "Keep mine" or their own typed version. `next` is what the
   * chat would have said next, shown once they decide. */
  pendingSuggestion?: { field: WordingField; index: number; suggestion: string; next: ResumeBuilderMessage[] };
  /** Text typed at a project question that reads like a request ("i want my
   * resume"), held while the candidate says whether it really is a project. */
  pendingProjectText?: string;
  /** "Build from my DigiDARA profile": the questions still to ask, in order --
   * only what the profile and the other agents could not fill in. */
  profileQueue?: ProfileQuestion[];
  /** The learner's degree from their profile, shown in the education question. */
  profileDegree?: string;
}
type ProfileQuestion = "phone" | "location" | "education" | "experience" | "project" | "linkedin" | "github";
type ResumeChatTurnHistory = Array<{ role: "student" | "agent"; text: string }>;
const HISTORY_LIMIT = 16;
export interface ResumeBuilderMessage { text: string; options?: ChatOption[]; }
export interface ResumeBuilderFlowResult { state: ResumeBuilderFlowState; messages: ResumeBuilderMessage[]; }
export const createInitialResumeBuilderState = (): ResumeBuilderFlowState => ({ step: "choose_workflow" });
const choices: ChatOption[] = [
  { label: "Create a resume", value: "new", description: "Start with a blank, editable resume." },
  { label: "Upload an existing resume", value: "upload", description: "Import PDF, DOC, DOCX, or TXT for review." },
  { label: "Paste your LinkedIn or notes", value: "paste_text", description: "Paste your LinkedIn profile text, or any rough notes." },
  { label: "Import your LinkedIn export", value: "import_linkedin_zip", description: "The ZIP from LinkedIn's own “Get a copy of your data” — your own data, no login sharing, no scraping." },
];
const FROM_PROFILE = "from_profile";
const fromProfileChoice: ChatOption = {
  label: "⭐ Build from my DigiDARA profile",
  value: FROM_PROFILE,
  description: "Uses your profile, capstone projects, certificates and coding results, and asks only what is missing.",
};
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

export function isKeyboardMashOrGibberish(text: string): boolean {
  const t = clean(text).toLowerCase();
  if (!t) return false;
  // 1. 3+ repeated identical characters (e.g. 'aaaa', 'zzzz')
  if (/([a-z])\1{2,}/i.test(t)) return true;
  // 2. 2-3 char looping sequences (e.g. 'asdasd', 'jkjkjk', 'ababab')
  if (t.length >= 4 && /^([a-z]{2,3})\1{2,}$/i.test(t)) return true;
  // 3. 4+ consecutive letters from QWERTY rows (forward and backward)
  const keyboardRows = [
    "qwertyuiop", "poiuytrewq",
    "asdfghjkl", "lkjhgfdsa",
    "zxcvbnm", "mnbvcxz",
  ];
  for (const row of keyboardRows) {
    for (let i = 0; i <= row.length - 4; i++) {
      const sub = row.substring(i, i + 4);
      if (t.includes(sub)) return true;
    }
  }
  // 4. 5+ consecutive consonants
  if (/[bcdfghjklmnpqrstvwxz]{5,}/i.test(t)) return true;
  // 5. Any word with length >= 4 having no vowels at all
  const words = t.split(/\s+/);
  for (const word of words) {
    if (word.length >= 4 && !/[aeiouy]/i.test(word)) return true;
  }
  return false;
}

export function isValidHumanCandidateName(text: string): boolean {
  const trimmed = clean(text);
  if (trimmed.length < 2 || trimmed.length > 50) return false;
  // Reject digits, email symbols, URLs, special punctuation
  if (/[\d@#$%^&*()_+<>{}[\]/\\~=]/.test(trimmed)) return false;
  // Reject questions or conversational commands
  if (/\?|^(can\s+you|what|how|why|who|help|hello|hi|hey|tell\s+me|show\s+me)\b/i.test(trimmed)) return false;
  // Reject keyboard-mash and gibberish (e.g. 'wertyui', 'qwerty', 'asdfgh', 'aaaa')
  if (isKeyboardMashOrGibberish(trimmed)) return false;
  // Reject academic degrees, education phrases, or role titles mistakenly entered as name
  const academicTerms = /\b(b\.?tech|b\.?e\.?|m\.?tech|m\.?e\.?|mca|bca|bsc|b\.?sc|bcom|b\.?com|mba|engineering|degree|diploma|college|university|school|computer\s+science|information\s+technology|data\s+science|developer|engineer|fresher|resume)\b/i;
  if (academicTerms.test(trimmed)) return false;
  return true;
}
/** Undergraduate degrees, written with or without dots: B.Com, BCom, B.Sc, B.E., BTech, B.Pharm, MBBS, LLB... */
const UG_DEGREE = /\b(b\.?\s?com|b\.?\s?sc|b\.?\s?c\.?\s?a|b\.?\s?tech|b\.?\s?e|b\.?\s?b\.?\s?a|b\.?\s?a|b\.?\s?pharm|b\.?\s?arch|b\.?\s?ed|b\.?\s?des|b\.?\s?voc|b\.?\s?lit|b\.?\s?s\.?\s?w|b\.?\s?h\.?\s?m|m\.?b\.?b\.?s|b\.?d\.?s|ll\.?b|bachelor(?:'?s)?)\b/i;
/** Postgraduate degrees: M.Com, M.Sc, MCA, M.E., M.Tech, MBA, M.A., M.Phil, LLM, PGDM... */
const PG_DEGREE = /\b(m\.?\s?com|m\.?\s?sc|m\.?\s?c\.?\s?a|m\.?\s?tech|m\.?\s?e|m\.?\s?b\.?\s?a|m\.?\s?a|m\.?\s?phil|m\.?\s?pharm|m\.?\s?arch|m\.?\s?ed|m\.?\s?s\.?\s?w|ll\.?m|pgdm|pgdca|master(?:'?s)?)\b/i;
const OTHER_QUALIFICATION = /\b(diploma|ph\.?\s?d|doctorate|hsc|sslc|12th|10th|higher secondary)\b/i;
const INSTITUTION = /\b(college|university|institute|institution|school|academy|polytechnic|iit|nit|iiit|campus)\b/i;

function hasUndergraduateEducation(education: ResumeCreateInput["education"] | undefined) {
  return (education || []).some((item) => {
    const level = String(item.level || "").toUpperCase();
    return level === "UG" || UG_DEGREE.test(String(item.degree || ""));
  });
}
function updateDraft(state: ResumeBuilderFlowState, draft: Partial<ResumeDraft>, step: ResumeBuilderStep): ResumeBuilderFlowState {
  return { ...state, step, draft: { ...state.draft, ...draft } };
}
function draftFromSavedResume(resume: Record<string, unknown>, fallback: ResumeDraft = {}): ResumeDraft {
  const personalInfo = resume.personal_info && typeof resume.personal_info === "object"
    ? resume.personal_info as Record<string, unknown>
    : {};
  const skills = Array.isArray(resume.skills)
    ? resume.skills.map((item) => typeof item === "string" ? item : String((item as { skill_name?: unknown }).skill_name || "")).filter(Boolean)
    : fallback.skills;
  return {
    ...fallback,
    title: String(resume.title || fallback.title || ""),
    name: String(personalInfo.name || fallback.name || ""),
    email: String(personalInfo.email || fallback.email || ""),
    phone: String(personalInfo.phone || fallback.phone || ""),
    location: String(personalInfo.location || fallback.location || ""),
    targetRole: String(resume.target_role || fallback.targetRole || ""),
    experienceLevel: (resume.experience_level === "fresher" || resume.experience_level === "experienced")
      ? resume.experience_level
      : fallback.experienceLevel,
    summary: String(resume.summary || fallback.summary || ""),
    skills,
    experience: Array.isArray(resume.experience) ? resume.experience as ResumeCreateInput["experience"] : fallback.experience,
    education: Array.isArray(resume.education) ? resume.education as ResumeCreateInput["education"] : fallback.education,
    projects: Array.isArray(resume.projects) ? resume.projects as ResumeCreateInput["projects"] : fallback.projects,
    certifications: Array.isArray(resume.certifications) ? resume.certifications as NonNullable<ResumeCreateInput["certifications"]> : fallback.certifications,
    achievements: Array.isArray(resume.achievements) ? resume.achievements as NonNullable<ResumeCreateInput["achievements"]> : fallback.achievements,
    links: Array.isArray(personalInfo.links) ? personalInfo.links.filter((item): item is string => typeof item === "string") : fallback.links,
  };
}
function missingRequiredDraftField(draft: ResumeDraft | undefined): { step: ResumeBuilderStep; message: string } | undefined {
  if (!draft?.title) return { step: "awaiting_title", message: "Your resume title is missing. What should we call this resume? For example: Data Analyst Resume." };
  if (!draft.name) return { step: "awaiting_name", message: "Your full name is missing. What name should appear on the resume?" };
  if (!draft.email) return { step: "awaiting_email", message: "Your email address is missing. What professional email should appear on the resume?" };
  if (!draft.targetRole) return { step: "awaiting_role", message: "Your target role is missing. What role are you applying for?" };
  if (!draft.experienceLevel) return { step: "awaiting_experience_level", message: "Your career level is missing. Please choose Fresher / student or Experienced professional." };
  return undefined;
}
function splitFields(value: string, expected: number) {
  const fields = value.split("|").map(clean);
  return fields.length >= expected && fields.slice(0, expected).every(Boolean) ? fields : null;
}
function educationLevel(degree: string, explicit = "") {
  if (explicit) return /^diploma$/i.test(explicit) ? "Diploma" : /^doctorate$/i.test(explicit) ? "Doctorate" : explicit.toUpperCase();
  if (PG_DEGREE.test(degree)) return "PG";
  if (UG_DEGREE.test(degree)) return "UG";
  if (/diploma/i.test(degree)) return "Diploma";
  if (/ph\.?d|doctor/i.test(degree)) return "Doctorate";
  return "";
}
/** Parse concise, user-supplied education without supplying any missing fact. */
export function parseEducationInput(value: string): ResumeCreateInput["education"] | { error: string } {
  // One entry per ";" or line, and a new entry wherever a "UG"/"PG" label starts.
  const entries = clean(value)
    .split(/\s*(?:;|\n)\s*|\s+(?=(?:UG|PG)\s*[:\-]\s)/i)
    .map(clean).filter(Boolean);
  const parsed: ResumeCreateInput["education"] = [];
  const labelPattern = /^\s*(UG|PG|Diploma|Doctorate)\s*(?:[:\-]|\s)\s*/i;
  for (const raw of entries) {
    const label = raw.match(labelPattern)?.[1] || "";
    const text = raw.replace(labelPattern, "")
      // "BCA from Nandha College" / "B.Com at XYZ College" / "B.Com in XYZ University"
      .replace(/\s+(?:from|at|in)\s+(?=[^,|]*\b(?:college|university|institute|school|academy|polytechnic)\b)/i, ", ");
    // Accept natural punctuation and either "college | degree" or
    // "degree | college". Candidate wording is retained verbatim.
    let values = text.split(/\s*(?:\||,|\s+-\s+)\s*/).map(clean).filter(Boolean);
    // "B.Com Nandha College 2019-2022" (no separators): split off the institution.
    if (values.length === 1) {
      const institution = values[0].match(/^(.*?)\s+((?:[A-Z][\w.&']*\s+)*?\S*\s*(?:college|university|institute|school|academy|polytechnic)\b.*)$/i);
      if (institution && (UG_DEGREE.test(institution[1]) || PG_DEGREE.test(institution[1]) || OTHER_QUALIFICATION.test(institution[1]))) {
        values = [institution[1], institution[2]].map(clean);
      }
    }
    const degreeIndex = values.findIndex((item) => UG_DEGREE.test(item) || PG_DEGREE.test(item) || OTHER_QUALIFICATION.test(item));
    const degree = degreeIndex >= 0 ? values[degreeIndex] : "";
    const years = text.match(/\b(19\d{2}|20\d{2})\b/g) || [];
    const cgpa = text.match(/\b(?:cgpa|gpa)\s*[:\-]?\s*(\d+(?:\.\d+)?(?:\s*\/\s*\d+(?:\.\d+)?)?)/i)?.[1]?.replace(/\s/g, "");
    const namedPercentage = text.match(/\b(?:percentage|percent)\s*[:=\-]?\s*(\d+(?:\.\d+)?%?)/i)?.[1]?.replace(/\s/g, "");
    const percentage = namedPercentage ? (namedPercentage.endsWith("%") ? namedPercentage : `${namedPercentage}%`) : (/%/.test(text) ? text.match(/\b(\d+(?:\.\d+)?%)/)?.[1] : undefined);
    const withoutYears = (item: string) => clean(item.replace(/\b(19\d{2}|20\d{2})\b(\s*(?:-|to|–)\s*\b(19\d{2}|20\d{2})\b)?/g, ""));
    const school = values
      .filter((item, index) => index !== degreeIndex && !/cgpa|gpa|percentage|percent|%/i.test(item))
      .map(withoutYears)
      .find((item) => item && (INSTITUTION.test(item) || !/^\d/.test(item))) || "";
    if (!degree || !school) {
      const understood = degree ? `I found the degree "${degree}" but not the college` : school ? `I found "${school}" but not the degree` : "I couldn't find a degree and college";
      return { error: `${understood} in "${raw}". Please write each qualification as degree, college, years - for example: UG: B.Com, Nandha College, 2019-2022; PG: M.Com, KSR College, 2022-2024.` };
    }
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
/** A phone number the way a recruiter can dial it: 10 digits (a leading 0 or
 * 91 is allowed), or a "+" country code with 8 to 15 digits in all. Spaces,
 * dashes, dots and brackets are fine. */
export function checkPhoneNumber(value: string): { value: string } | { error: string } {
  const text = clean(value);
  if (/[^\d+\s().-]/.test(text) || (text.match(/\+/g) || []).length > 1 || (text.includes("+") && !text.startsWith("+"))) {
    return { error: "A phone number can only contain digits (with an optional + country code). Please type it again, for example 98765 43210, or type Skip." };
  }
  const digits = text.replace(/\D/g, "");
  const valid = text.startsWith("+")
    ? digits.length >= 8 && digits.length <= 15
    : digits.length === 10 || (digits.length === 11 && digits.startsWith("0")) || (digits.length === 12 && digits.startsWith("91"));
  if (valid) return { value: text };
  return {
    error: `"${text}" has ${digits.length} digit${digits.length === 1 ? "" : "s"}, so it isn't a complete phone number. A mobile number needs 10 digits, for example 98765 43210 - or add the country code, like +91 98765 43210. Please type it again, or type Skip.`,
  };
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
    project: "Add a project using normal text, for example: Sales Dashboard, built a Power BI dashboard that reduced reporting time. Type Skip to omit it.",
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

const WAIVE_UG = "waive_ug";

/** A fresher resume needs a UG degree. Says what is already saved, shows the
 * format, and offers a way on for a candidate who genuinely has none (for
 * example a diploma holder) -- instead of a Skip button that led straight back
 * here. */
function ugRequiredMessage(education: ResumeCreateInput["education"] | undefined): ResumeBuilderMessage {
  const saved = (education || []).map((item) => `${item.degree || item.level || "Qualification"} at ${item.school}`).join("; ");
  return {
    text: `A fresher resume needs your undergraduate (UG) degree.${saved ? ` I have saved: ${saved}, but no UG degree.` : ""}\n\nType it as degree, college, years - for example: UG: B.Com, Nandha College, 2019-2022. You can add your PG in the same message: UG: B.Com, Nandha College, 2019-2022; PG: M.Com, KSR College, 2022-2024.`,
    options: [{ label: "Continue without a UG degree", value: WAIVE_UG, description: "Only if you do not have one (for example, a diploma holder)." }],
  };
}

async function createFromDraft(state: ResumeBuilderFlowState, user: User): Promise<ResumeBuilderFlowResult> {
  const candidateDraft = state.draft;
  const missing = missingRequiredDraftField(candidateDraft);
  if (missing) {
    return { state: { ...state, step: missing.step, error: undefined }, messages: [{ text: `${missing.message} Your other resume details are still saved.` }] };
  }
  const draft = candidateDraft as ResumeDraft & { title: string; name: string; email: string; targetRole: string; experienceLevel: "fresher" | "experienced" };

  if (draft.experienceLevel === "fresher" && !hasUndergraduateEducation(draft.education) && !draft.skipEducation) {
    return {
      state: { ...state, step: "awaiting_education", pendingField: "education.ug" },
      messages: [ugRequiredMessage(draft.education)],
    };
  }
  if (!(draft.projects?.length || draft.experience?.length)) {
    return {
      state: { ...state, step: "awaiting_project" },
      messages: [{ text: "Add at least one project or experience entry before generating your resume. Short project details are enough for AI to improve later." }],
    };
  }
  try {
    const resumeInput: ResumeCreateInput = {
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
    };
    const resume = state.resumeId
      ? await updateResume(user.id, state.resumeId, { ...(await getResume(user.id, state.resumeId)), ...resumeInput })
      : await createResume(user.id, resumeInput);
    const id = Number(resume.id);
    return { state: { ...state, step: "reviewing", resumeId: id, resumeTitle: String(resume.title || draft.title) }, messages: [{ text: state.resumeId ? "Your enriched details were saved to the existing resume. You can continue editing or generate final wording." : "Your resume has been saved from the details you verified. You can edit it in plain language, then choose Generate final wording to create the complete target-role-focused version.", options: reviewOptions }] };
  } catch (error) {
    return { state: { ...state, step: "confirming", error: (error as Error).message }, messages: [{ text: `I couldn’t create the resume: ${(error as Error).message}\n\nYour details are still saved. Type the correction here - for example "the start date for my internship is Jan 2022" - and I'll fix it, then choose Try creating again.`, options: [{ label: "Try creating again", value: "create_now" }, ...restartOption] }] };
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


/** A question with the learner's saved answer from onboarding as a one-tap
 * option, so they never retype what DigiDARA already knows. */
function roleQuestion(text: string): ResumeBuilderMessage {
  const goal = learnerGoal();
  return goal ? { text, options: [{ label: `${displayRole(goal.targetRole)} (from your profile)`, value: displayRole(goal.targetRole) }] } : { text };
}

function skillsQuestion(text: string): ResumeBuilderMessage {
  const goal = learnerGoal();
  return goal && goal.skills.length
    ? { text, options: [{ label: `Use my skills: ${goal.skills.slice(0, 6).join(", ")}`, value: goal.skills.join(", ") }] }
    : { text };
}

/** The experience question, with the learner's own answer marked. */
function experienceLevelOptions(fresher: string, experienced: string): ChatOption[] {
  const mine = learnerGoal()?.experience;
  return [
    { label: mine === "fresher" ? "Fresher / student · from your profile" : "Fresher / student", value: "fresher", description: fresher },
    { label: mine === "experienced" ? "Experienced professional · from your profile" : "Experienced professional", value: "experienced", description: experienced },
  ];
}

export async function openResumeBuilderChat(user: User): Promise<ResumeBuilderFlowResult> {
  const state = createInitialResumeBuilderState();
  try {
    await ensureResumeProfile(user.id, user.name, user.email);
    const goal = learnerGoal();
    const text = goal
      ? `Hi ${user.name.split(" ")[0]}! I can build your ${displayRole(goal.targetRole)} resume from what DigiDARA already knows about you, and ask only for what is missing. Or start another way:`
      : `Hi ${user.name.split(" ")[0]}! Would you like to create a new resume or upload one to improve?`;
    return { state, messages: [{ text, options: goal ? [fromProfileChoice, ...choices] : choices }] };
  }
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

const PROFILE_STEPS: Record<ProfileQuestion, ResumeBuilderStep> = {
  phone: "awaiting_phone", location: "awaiting_location", education: "awaiting_education", experience: "awaiting_experience",
  project: "awaiting_project", linkedin: "awaiting_linkedin", github: "awaiting_github",
};
const PROFILE_ORDER: ProfileQuestion[] = ["phone", "location", "education", "experience", "project", "linkedin", "github"];
// "Add another?" steps: the candidate is still on the same section.
const MORE_STEPS = new Set<ResumeBuilderStep>(["awaiting_education_more", "awaiting_experience_more", "awaiting_project_more"]);

function profileQuestionMessage(question: ProfileQuestion, state: ResumeBuilderFlowState): ResumeBuilderMessage {
  if (question === "education" && state.profileDegree) {
    const degree = state.profileDegree;
    return {
      text: `Your profile says you studied **${degree}**. Add the college and years, for example: UG: ${degree}, KSR College, 2021-2024, CGPA: 8.2. Add a PG the same way after a semicolon.`,
      options: skipOption,
    };
  }
  const prompt = draftFieldPrompt(question, state.draft);
  return { text: prompt, options: /Skip/.test(prompt) ? skipOption : undefined };
}

/** The draft, filled from what DigiDARA knows -- nothing invented. */
export function draftFromResumeFacts(facts: ResumeFacts): ResumeDraft {
  const role = displayRole(facts.target_role || "");
  const projectSkills = (facts.projects || []).flatMap((p) => p.skills || []);
  const skills = [...facts.skills, ...projectSkills].filter((s, i, all) => all.findIndex((t) => t.toLowerCase() === s.toLowerCase()) === i);
  return {
    title: role ? `${role} Resume` : "My Resume",
    name: facts.name, email: facts.email, phone: facts.phone || undefined,
    targetRole: role || undefined, experienceLevel: facts.experience_level,
    skills: skills.slice(0, 20),
    projects: (facts.projects || []).map((p) => ({
      title: p.title,
      description: [p.description, p.skills?.length ? `Technologies: ${p.skills.join(", ")}.` : ""].filter(Boolean).join(" "),
    })),
    certifications: (facts.certifications || []).map((c) => ({
      name: c.name, issuer: c.issuer, issue_date: c.date,
      description: typeof c.score === "number" ? `Scored ${Math.round(c.score)}% in the certification exam.` : undefined,
    })),
    achievements: (facts.achievements || []).map((a) => ({ title: a.title, description: a.description, organization: "DigiDARA" })),
  };
}

function foundSummary(facts: ResumeFacts, draft: ResumeDraft): string {
  const lines = [
    `• ${draft.name} — ${draft.email}${draft.phone ? ` — ${draft.phone}` : ""}`,
    `• Target role: ${draft.targetRole || "not set"} (${draft.experienceLevel === "experienced" ? "Experienced" : "Fresher"})`,
    `• Skills: ${(draft.skills || []).join(", ") || "none yet"}`,
  ];
  if (draft.projects?.length) lines.push(`• Projects: ${draft.projects.map((p) => p.title).join("; ")}`);
  if (draft.certifications?.length) lines.push(`• Certifications: ${draft.certifications.map((c) => c.name).join("; ")}`);
  if (draft.achievements?.length) lines.push(`• Achievements: ${draft.achievements.map((a) => a.title).join("; ")}`);
  const from = facts.sources.length ? ` (from your profile and ${facts.sources.join(", ")})` : " (from your profile)";
  return `Here is what I already have${from}:\n${lines.join("\n")}`;
}

async function startFromProfile(state: ResumeBuilderFlowState, user: User): Promise<ResumeBuilderFlowResult> {
  let facts: ResumeFacts;
  try {
    facts = await fetchResumeFacts();
  } catch (error) {
    return { state, messages: [{ text: `${(error as Error).message} You can still create a resume step by step.`, options: choices }] };
  }
  const draft = draftFromResumeFacts({ ...facts, name: facts.name || user.name, email: facts.email || user.email });
  const queue = PROFILE_ORDER.filter((question) => facts.missing.includes(question));
  const next: ResumeBuilderFlowState = { ...state, draft, profileDegree: facts.degree || undefined, error: undefined };
  const summary = foundSummary(facts, draft);
  if (!queue.length) return { state: { ...next, step: "confirming" }, messages: [{ text: summary }, reviewMessage(draft)] };
  const [first, ...rest] = queue;
  return {
    state: { ...next, step: PROFILE_STEPS[first], profileQueue: rest },
    messages: [
      { text: `${summary}\n\nI only need ${queue.length} more detail${queue.length === 1 ? "" : "s"}. Type Skip for anything you do not want on the resume.` },
      profileQuestionMessage(first, next),
    ],
  };
}

/** In "Build from my DigiDARA profile", once a question is answered, go to
 * the next missing detail instead of the question that normally follows --
 * the rest is already filled in. With none left, show the review. */
function continueProfileQueue(previous: ResumeBuilderFlowState, value: string, result: ResumeBuilderFlowResult): ResumeBuilderFlowResult {
  const queue = previous.profileQueue;
  if (!queue || previous.returnTo || requestedDraftField(value)) return result;
  const step = result.state.step;
  // Not accepted yet, or adding another entry to the same section: keep waiting.
  if (step === previous.step || MORE_STEPS.has(step)) return { ...result, state: { ...result.state, profileQueue: queue } };
  // Anything other than moving on to another question (a created resume, an error, a restart) ends the queue.
  if (!DRAFT_STEPS.has(step) || step === "awaiting_enrichment_choice") return { ...result, state: { ...result.state, profileQueue: undefined } };
  const draft = result.state.draft || {};
  if (!queue.length) {
    return { state: { ...result.state, step: "confirming", profileQueue: undefined }, messages: [{ text: "Thanks, that is everything I needed." }, reviewMessage(draft)] };
  }
  const [nextQuestion, ...rest] = queue;
  const nextState = { ...result.state, step: PROFILE_STEPS[nextQuestion], profileQueue: rest };
  return { state: nextState, messages: [{ text: "Got it." }, profileQuestionMessage(nextQuestion, nextState)] };
}

/** Steps where the candidate is still building the draft (before a resume
 * exists): a typed correction is applied to the draft by the assistant. */
const DRAFT_STEPS = new Set<ResumeBuilderStep>([
  "awaiting_title", "awaiting_name", "awaiting_email", "awaiting_phone", "awaiting_location", "awaiting_role",
  "awaiting_summary", "awaiting_skills", "awaiting_experience", "awaiting_experience_more", "awaiting_education",
  "awaiting_education_more", "awaiting_project", "awaiting_project_more", "awaiting_linkedin", "awaiting_github",
  "awaiting_portfolio", "awaiting_certifications", "awaiting_certifications_more", "awaiting_achievements",
  "awaiting_achievements_more", "confirming", "awaiting_enrichment_choice",
]);

/** "change my college to ...", "the start date is Jan 2022", "my PG is MCA not MBA", "remove the second project". */
const EDIT_REQUEST = /^(?:please\s+|pls\s+|can you\s+|could you\s+|i\s+(?:want|need|would like)\s+to\s+)*(?:change|edit|update|correct|fix|replace|rename|remove|delete)\b|\b(?:is wrong|was wrong|are wrong|typo|mistake|instead of)\b|^(?:my|the)\s+[\w\s]{2,40}?\s+(?:is|was|should be|are)\b/i;

function lastAgentText(state: ResumeBuilderFlowState): string {
  return [...(state.history || [])].reverse().find((turn) => turn.role === "agent")?.text || "";
}

async function askAssistant(state: ResumeBuilderFlowState, user: User, value: string) {
  return resumeChatTurn(user.id, {
    message: value,
    step: state.step,
    asked: lastAgentText(state),
    draft: (state.draft || {}) as Record<string, unknown>,
    history: state.history || [],
  });
}

/** The assistant's reading of an education answer the parser could not read. */
async function educationFromAssistant(state: ResumeBuilderFlowState, user: User, value: string): Promise<ResumeCreateInput["education"] | undefined> {
  try {
    const turn = await askAssistant(state, user, value);
    const education = turn.updates.education;
    if (!Array.isArray(education) || !education.length) return undefined;
    // The assistant returns the complete list: keep only what this message added.
    const known = new Set((state.draft?.education || []).map((item) => `${item.degree}|${item.school}`.toLowerCase()));
    const added = (education as ResumeCreateInput["education"]).filter((item) => !known.has(`${item.degree}|${item.school}`.toLowerCase()));
    return added.length ? added : undefined;
  } catch {
    return undefined;
  }
}

/** A typed correction while the draft is being built, applied by the
 * assistant. Returns undefined to fall through to the step's own handling. */
async function applyTypedEdit(state: ResumeBuilderFlowState, user: User, value: string): Promise<ResumeBuilderFlowResult | undefined> {
  if (!DRAFT_STEPS.has(state.step) || !EDIT_REQUEST.test(value) || value.length > 1500) return undefined;
  // "change my education" on its own (no new value given): jump to that
  // section, as before. "change my name to Prem" carries the value: apply it.
  const request = clean(value).replace(/^i\s+(?:want|need)\s+to\s+/i, "");
  if (requestedDraftField(value) && !/\s(?:to|is|as|into)\s/i.test(request)) return undefined;
  let turn;
  try {
    turn = await askAssistant(state, user, value);
  } catch (error) {
    return { state, messages: [{ text: `I couldn't apply that change right now (${(error as Error).message}). Please try again in a moment - your details are still saved.` }] };
  }
  if (turn.intent !== "edit" && turn.intent !== "answer") {
    return turn.reply ? { state, messages: [{ text: turn.reply }] } : undefined;
  }
  // An answer to the question being asked is saved by that step's own
  // handling, which also moves the chat on to the next question.
  if (turn.intent === "answer" && state.step !== "confirming" && state.step !== "awaiting_enrichment_choice") return undefined;
  const updates = turn.updates as Partial<ResumeDraft>;
  if (!Object.keys(updates).length) return turn.reply ? { state, messages: [{ text: turn.reply }] } : undefined;
  if (updates.phone) {
    const phone = checkPhoneNumber(updates.phone);
    if ("error" in phone) return { state, messages: [{ text: phone.error }] };
  }
  const draft: ResumeDraft = { ...state.draft, ...updates };
  const ugNowPresent = state.pendingField === "education.ug" && hasUndergraduateEducation(draft.education);
  const next: ResumeBuilderFlowState = {
    ...state,
    draft,
    error: undefined,
    ...(ugNowPresent ? { step: "confirming" as const, pendingField: undefined } : {}),
  };
  const reply = turn.reply || "Done - I've updated your details.";
  return {
    state: next,
    messages: next.step === "confirming" ? [{ text: reply }, reviewMessage(draft)] : [{ text: `${reply}\n\nYou can carry on from where we were.` }],
  };
}

function withHistory(result: ResumeBuilderFlowResult, previous: ResumeChatTurnHistory, studentText: string): ResumeBuilderFlowResult {
  const history: ResumeChatTurnHistory = [
    ...previous,
    { role: "student" as const, text: studentText },
    ...result.messages.map((message) => ({ role: "agent" as const, text: message.text })),
  ].slice(-HISTORY_LIMIT);
  const lastMessage = result.messages.length ? result.messages[result.messages.length - 1] : result.state.lastMessage;
  return { ...result, state: { ...result.state, history, lastMessage } };
}

/** After "change my <field>", once that field is saved the step handler moves
 * on to the question after it. Go back to where the candidate was instead. */
function returnAfterFieldEdit(previous: ResumeBuilderFlowState, value: string, result: ResumeBuilderFlowResult): ResumeBuilderFlowResult {
  const returnTo = previous.returnTo;
  if (!returnTo) return result;
  // A jump to yet another field: keep the original place to come back to.
  if (requestedDraftField(value)) return result;
  // Still on the edited field (the answer was not accepted): keep waiting.
  if (result.state.step === previous.step) return { ...result, state: { ...result.state, returnTo } };
  // Anything other than simply moving on to another question (an error, a
  // restart, a created resume) is left as it is, without the return.
  if (!DRAFT_STEPS.has(result.state.step)) return { ...result, state: { ...result.state, returnTo: undefined } };
  const draft = result.state.draft || {};
  const back = returnTo.step === "confirming" || !returnTo.message ? reviewMessage(draft) : returnTo.message;
  return {
    state: { ...result.state, step: returnTo.step === "confirming" || !returnTo.message ? "confirming" : returnTo.step, returnTo: undefined },
    messages: [{ text: "Saved. Now back to where we were:" }, back],
  };
}

/** Text typed at a project question that is a request, not a project:
 * "i want my resume", "create my resume", "done", "that's all". */
const PROJECT_REQUEST = /^(?:i\s+(?:want|need|would like)|give me|can you|could you|please|show me)\b[^.]*\b(?:resume|cv|pdf|download|next|done|finish)\b|^(?:done|finish(?:ed)?|that'?s all|no more(?: projects?)?|nothing (?:else|more)|(?:generate|create|make|build|download)(?: my| the)? (?:resume|cv)(?: now)?|(?:i want )?my (?:resume|cv))\W*$/i;
const CONFIRM_PROJECT = "confirm_project";

function projectOrRequest(state: ResumeBuilderFlowState, value: string): ResumeBuilderFlowResult | undefined {
  if (!PROJECT_REQUEST.test(clean(value))) return undefined;
  const first = state.step === "awaiting_project";
  return {
    state: { ...state, pendingProjectText: clean(value) },
    messages: [{
      text: `Did you mean "${clean(value)}" as a project, or do you want to ${first ? "skip projects for now" : "move on and finish your resume"}?`,
      options: [
        first
          ? { label: "Skip projects", value: "skip", description: "Continue without adding a project." }
          : { label: "Move on to the next section", value: "next_section", description: "Stop adding projects and continue to your links." },
        { label: "Add it as a project", value: CONFIRM_PROJECT, description: `Save "${clean(value)}" as a project.` },
      ],
    }],
  };
}

type RemovableSection = "projects" | "experience" | "education" | "certifications" | "achievements";
const SECTION_WORDS: Array<[RegExp, RemovableSection, string]> = [
  [/\bprojects?\b/i, "projects", "project"],
  [/\b(experiences?|internships?|jobs?|work)\b/i, "experience", "experience"],
  [/\b(education|degrees?|college|qualifications?)\b/i, "education", "education"],
  [/\bcertifications?|certificates?\b/i, "certifications", "certification"],
  [/\bachievements?|awards?\b/i, "achievements", "achievement"],
];
const ORDINALS: Record<string, number> = { first: 1, second: 2, third: 3, fourth: 4, fifth: 5, sixth: 6, last: -1 };

/** Words too common in titles to identify one entry on their own. */
const GENERIC_TITLE_WORDS = new Set(["project", "projects", "system", "application", "website", "using", "based", "management", "with", "from", "that", "this", "only", "delete", "remove"]);

function entryTitle(entry: Record<string, unknown>) {
  return String(entry.title || entry.name || [entry.role, entry.company].filter(Boolean).join(" at ") || [entry.degree, entry.school].filter(Boolean).join(", ") || "");
}

function words(text: string) {
  return text.toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter(Boolean);
}

/** Two words match when equal, or when long enough and one typo apart ("resuem" / "resume"). */
function similarWord(a: string, b: string) {
  if (a === b) return true;
  if (a.length < 4 || b.length < 4 || Math.abs(a.length - b.length) > 1) return false;
  const sorted = (word: string) => word.split("").sort().join("");
  if (a.length === b.length && sorted(a) === sorted(b)) return true;
  let i = 0; let j = 0; let edits = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { i += 1; j += 1; continue; }
    edits += 1;
    if (edits > 1) return false;
    if (a.length > b.length) i += 1; else if (b.length > a.length) j += 1; else { i += 1; j += 1; }
  }
  return edits + (a.length - i) + (b.length - j) <= 1;
}

/** "delete the 2 project", "remove the second project", "delete the i want my
 * resuem project only": exactly which one entry to remove, or undefined when
 * the request does not say clearly (the AI edit handles it then). */
function entryToRemove(value: string, resume: Record<string, unknown>): { section: RemovableSection; label: string; index: number; title: string } | undefined {
  const text = clean(value);
  if (!/\b(delete|remove|drop|take out|get rid of)\b/i.test(text)) return undefined;
  const found = SECTION_WORDS.find(([pattern]) => pattern.test(text));
  if (!found) return undefined;
  const [, section, label] = found;
  const entries = Array.isArray(resume[section]) ? resume[section] as Array<Record<string, unknown>> : [];
  if (!entries.length) return undefined;

  const numbered = text.match(/\b(\d{1,2})(?:st|nd|rd|th)?\b/)?.[1];
  const ordinal = Object.entries(ORDINALS).find(([word]) => new RegExp(`\\b${word}\\b`, "i").test(text))?.[1];
  const position = numbered ? Number(numbered) : ordinal;
  if (position !== undefined) {
    const index = position === -1 ? entries.length - 1 : position - 1;
    return index >= 0 && index < entries.length ? { section, label, index, title: entryTitle(entries[index]) } : undefined;
  }

  // By name: the entry whose title words best appear in the request -- most
  // of the title ("i want my resuem" for "I Want My Resume"), or one
  // distinctive word that only that entry has ("parkinson").
  const requestWords = words(text);
  const scored = entries.map((entry, index) => {
    const titleWords = words(entryTitle(entry));
    const matched = titleWords.filter((word) => requestWords.some((candidate) => similarWord(word, candidate)));
    return {
      index,
      score: titleWords.length ? matched.length / titleWords.length : 0,
      distinctive: matched.filter((word) => word.length >= 4 && !GENERIC_TITLE_WORDS.has(word)).length,
    };
  });
  const byScore = [...scored].sort((a, b) => b.score - a.score);
  if (byScore[0].score >= 0.6 && byScore[0].score !== byScore[1]?.score) {
    return { section, label, index: byScore[0].index, title: entryTitle(entries[byScore[0].index]) };
  }
  const distinctive = scored.filter((entry) => entry.distinctive > 0);
  if (distinctive.length === 1) {
    return { section, label, index: distinctive[0].index, title: entryTitle(entries[distinctive[0].index]) };
  }
  return undefined;
}

const USE_SUGGESTION = "use_suggestion";
const KEEP_MINE = "keep_mine";
const WORDING_LABEL: Record<WordingField, string> = { summary: "summary", project: "project description", experience: "experience description" };

/** What the candidate just wrote in a summary, project or experience answer:
 * the field, which entry, and the text -- or undefined when the step did not
 * save exactly one new piece of free text. */
function newlyWritten(previous: ResumeBuilderFlowState, result: ResumeBuilderFlowResult): { field: WordingField; index: number; text: string } | undefined {
  const before = previous.draft || {};
  const after = result.state.draft || {};
  if (previous.step === "awaiting_summary" && after.summary && after.summary !== before.summary) {
    return { field: "summary", index: 0, text: after.summary };
  }
  if (previous.step === "awaiting_project" && (after.projects?.length || 0) === (before.projects?.length || 0) + 1) {
    const index = after.projects!.length - 1;
    return { field: "project", index, text: String(after.projects![index].description || "") };
  }
  if (previous.step === "awaiting_experience" && (after.experience?.length || 0) === (before.experience?.length || 0) + 1) {
    const index = after.experience!.length - 1;
    return { field: "experience", index, text: String(after.experience![index].raw_input || "") };
  }
  return undefined;
}

/** After a summary, project or experience answer is saved, offer a stronger
 * wording to use or ignore. Any failure just carries on without one. */
async function offerWordingSuggestion(previous: ResumeBuilderFlowState, result: ResumeBuilderFlowResult, user: User): Promise<ResumeBuilderFlowResult> {
  if (previous.returnTo || result.state.step === previous.step) return result;
  const written = newlyWritten(previous, result);
  if (!written || written.text.trim().length < 30) return result;
  let suggestion: string | null = null;
  try {
    suggestion = await suggestResumeWording(user.id, written.field, written.text, result.state.draft?.targetRole);
  } catch {
    return result;
  }
  if (!suggestion) return result;
  return {
    state: { ...result.state, pendingSuggestion: { field: written.field, index: written.index, suggestion, next: result.messages } },
    messages: [{
      text: `💡 Here is a stronger way to write your ${WORDING_LABEL[written.field]}:\n\n"${suggestion}"\n\nUse it, keep yours, or type your own version.`,
      options: [
        { label: "Use this", value: USE_SUGGESTION, description: "Replace your text with this wording." },
        { label: "Keep mine", value: KEEP_MINE, description: "Keep exactly what you wrote." },
      ],
    }],
  };
}

function withWording(draft: ResumeDraft, field: WordingField, index: number, text: string): ResumeDraft {
  if (field === "summary") return { ...draft, summary: text };
  if (field === "project") {
    return { ...draft, projects: (draft.projects || []).map((project, i) => i === index ? { ...project, description: text } : project) };
  }
  return { ...draft, experience: (draft.experience || []).map((entry, i) => i === index ? { ...entry, raw_input: text } : entry) };
}

/** "Use this", "Keep mine", or the candidate's own new version -- then on to
 * whatever the chat was going to ask next. */
function resolveWordingSuggestion(state: ResumeBuilderFlowState, value: string): ResumeBuilderFlowResult {
  const pending = state.pendingSuggestion!;
  const typed = clean(value);
  const keep = value === KEEP_MINE || isSkip(value) || /^keep( mine| it| my (own|version))?$/i.test(typed);
  const use = value === USE_SUGGESTION || /^(use( this| it)?|yes|ok(ay)?|accept)$/i.test(typed);
  const next = { ...state, pendingSuggestion: undefined };
  if (keep || !typed) return { state: next, messages: [{ text: "Okay - keeping your wording." }, ...pending.next] };
  const text = use ? pending.suggestion : typed;
  return {
    state: { ...next, draft: withWording(state.draft || {}, pending.field, pending.index, text) },
    messages: [{ text: use ? "Done - I've used the suggested wording." : "Saved your version." }, ...pending.next],
  };
}

export async function handleResumeBuilderText(state: ResumeBuilderFlowState, user: User, value: string): Promise<ResumeBuilderFlowResult> {
  const restarting = value === "restart" || clean(value).toLowerCase() === "start over";
  if (state.pendingSuggestion && !restarting) return withHistory(resolveWordingSuggestion(state, value), state.history || [], value);
  const edited = restarting ? undefined : await applyTypedEdit(state, user, value);
  const result = edited ?? await offerWordingSuggestion(state, continueProfileQueue(state, value, returnAfterFieldEdit(state, value, await handleResumeBuilderStep(state, user, value))), user);
  return withHistory(result, restarting ? [] : state.history || [], value);
}

async function handleResumeBuilderStep(state: ResumeBuilderFlowState, user: User, value: string): Promise<ResumeBuilderFlowResult> {
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
      messages: [roleQuestion("What role are you targeting with this resume? For example: Data Analyst or Python Developer.")],
    };
  }

  if (isCreateResumeIntent(value) && (state.step === "choose_workflow" || state.step === "error" || state.step === "awaiting_experience_level")) {
    if (state.step === "awaiting_experience_level") {
      return { state, messages: [{ text: "Before we begin, which best describes you? This sets the right resume length and section priorities.", options: experienceLevelOptions("A concise, one-page resume focused on education, projects, skills, and internships.", "A resume designed for up to two pages, with room for career impact and achievements.") }] };
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
      messages: [roleQuestion("What role are you targeting with this resume? For example: Data Analyst or Python Developer.")],
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
    // Remember the question the candidate was on (unless they are already
    // editing that same field), to come back to it once this field is saved.
    const returnTo = state.returnTo ?? (state.step !== draftField ? { step: state.step, message: state.lastMessage } : undefined);
    return { state: { ...state, step: draftField, returnTo }, messages: [{ text: draftFieldPrompt(draftField.replace("awaiting_", ""), state.draft) }] };
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
    let draft = state.draft || {};
    if (state.resumeId) {
      try {
        draft = draftFromSavedResume(await getResume(user.id, state.resumeId), draft);
      } catch (error) {
        return { state, messages: [{ text: `I could not load your saved resume for enrichment: ${(error as Error).message}. Please try again.` }] };
      }
    }
    return {
      state: { ...state, step: "awaiting_enrichment_choice", draft },
      messages: [enrichmentChoiceMessage(draft)],
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
      // Removing one named or numbered entry is done exactly, not left to the
      // AI (which removed the wrong project, or both, for such requests).
      const removal = entryToRemove(value, currentResume);
      const proposal = removal
        ? {
            resume: { ...currentResume, [removal.section]: (currentResume[removal.section] as unknown[]).filter((_, index) => index !== removal.index) },
            changes: [`Removed ${removal.label} ${removal.index + 1}: "${removal.title}". Everything else is unchanged.`],
            warnings: [],
            requires_confirmation: true,
          }
        : await suggestResumeEdit(user.id, currentResume, clean(value));
      return {
        state: { ...state, step: "awaiting_edit_confirmation", pendingEdit: proposal },
        messages: [{ text: formatEditProposal(proposal), options: editConfirmationOptions }],
      };
    } catch (error) {
      return { state: { ...state, step: "reviewing" }, messages: [{ text: `I could not prepare a safe edit proposal: ${(error as Error).message}. Your resume was not changed.`, options: reviewOptions }] };
    }
  }
  if (state.step === "choose_workflow") {
    if (value === FROM_PROFILE) return startFromProfile(state, user);
    if (value === "new") return { state: { ...state, step: "awaiting_experience_level", draft: {} }, messages: [{ text: "Before we begin, which best describes you? This sets the right resume length and section priorities.", options: experienceLevelOptions("A concise, one-page resume focused on education, projects, skills, and internships.", "A resume designed for up to two pages, with room for career impact and achievements.") }] };
    if (value === "upload") return { state: { ...state, step: "awaiting_upload_role", draft: {} }, messages: [roleQuestion("What role are you targeting with this resume? For example: Data Analyst or Python Developer.")] };
    if (value === "paste_text") return { state: { ...state, step: "awaiting_paste_text", draft: {} }, messages: [{ text: "Paste your LinkedIn “About” and experience text, or any rough notes about your background, and I'll turn it into a resume." }] };
    if (value === "import_linkedin_zip") return { state: { ...state, step: "awaiting_import_zip", draft: {} }, messages: [{ text: "Attach the ZIP using the paperclip button. On LinkedIn: Settings & Privacy → Data privacy → Get a copy of your data. It can take LinkedIn a little while to prepare it — come back here once you have the download." }] };
  }
  if (state.step === "awaiting_paste_text") {
    const text = clean(value);
    if (text.length < 20) return { state, messages: [{ text: "That looks too short to extract a resume from — paste more of your LinkedIn “About”/experience text or notes." }] };
    return importResumeBuilderFile(state, user, new File([text], "pasted-notes.txt", { type: "text/plain" }));
  }
  if (state.step === "awaiting_import_zip") {
    return { state, messages: [{ text: "Attach the LinkedIn export ZIP using the paperclip button whenever you have it." }] };
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
    const candidateName = clean(value);
    if (!isValidHumanCandidateName(candidateName)) {
      return {
        state,
        messages: [{
          text: "Please enter your real full name (for example, ‘Priya Sharma’ or ‘Arun Kumar’) rather than educational qualifications, random characters, or questions.",
        }],
      };
    }
    return { state: updateDraft(state, { name: candidateName }, "awaiting_email"), messages: [{ text: "What is your professional email address?" }] };
  }
  if (state.step === "awaiting_email") {
    const email = clean(value).toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return { state, messages: [{ text: "Please enter a valid email address, for example name@example.com." }] };
    return { state: updateDraft(state, { email }, "awaiting_phone"), messages: [{ text: "What is your phone number? Type Skip if you prefer not to include one.", options: skipOption }] };
  }
  if (state.step === "awaiting_phone") {
    if (!isSkip(value)) {
      const phone = checkPhoneNumber(value);
      if ("error" in phone) return { state, messages: [{ text: phone.error, options: skipOption }] };
    }
    return { state: updateDraft(state, { phone: isSkip(value) ? "" : clean(value) }, "awaiting_location"), messages: [{ text: "What city and country should appear on your resume? Type Skip to omit it.", options: skipOption }] };
  }
  if (state.step === "awaiting_location") return { state: updateDraft(state, { location: isSkip(value) ? "" : normalizeLocation(value) }, "awaiting_role"), messages: [roleQuestion("What role are you targeting? For example: Data Analyst or Frontend Developer.")] };
  if (state.step === "awaiting_role") {
    if (clean(value).length < 2) return { state, messages: [{ text: "Please enter the role you are targeting." }] };
    return { state: updateDraft(state, { targetRole: clean(value).replace(/^role\s*:\s*/i, "") }, "awaiting_summary"), messages: [{ text: "Write a short summary, share a few facts, or type Skip. You can improve it later with AI.", options: skipOption }] };
  }
  if (state.step === "awaiting_summary") {
    if (isSkip(value) || (clean(value).length >= 3 && clean(value).length < 30)) {
      return { state: updateDraft(state, { summary: isSkip(value) ? "" : clean(value) }, "awaiting_skills"), messages: [skillsQuestion("List your key skills, separated by commas. For example: Python, SQL, Power BI, Excel.")] };
    }
    if (clean(value).length < 30) return { state, messages: [{ text: "Please add a little more detail—at least 30 characters makes your summary useful to recruiters." }] };
    return { state: updateDraft(state, { summary: clean(value) }, "awaiting_skills"), messages: [skillsQuestion("List your key skills, separated by commas. For example: Python, SQL, Power BI, Excel.")] };
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
    if (value === WAIVE_UG) {
      const next = updateDraft({ ...state, pendingField: undefined }, { skipEducation: true }, "confirming");
      return { state: next, messages: [{ text: "Okay - I'll create your resume without a UG degree." }, reviewMessage(next.draft || {})] };
    }
    if (isSkip(value)) {
      if (state.pendingField === "education.ug") {
        return { state, messages: [ugRequiredMessage(state.draft?.education)] };
      }
      return { state: updateDraft(state, {}, "awaiting_project"), messages: [{ text: "Add one relevant project using normal text, for example: Sales Dashboard, built a Power BI dashboard for weekly reporting. Type Skip to omit it.", options: skipOption }] };
    }
    let education = parseEducationInput(value);
    if (!Array.isArray(education)) {
      // Written in a shape the parser does not know: let the assistant read it.
      const understood = await educationFromAssistant(state, user, value);
      if (!understood) {
        return { state, messages: [state.pendingField === "education.ug" ? { text: education.error, options: ugRequiredMessage(state.draft?.education).options } : { text: education.error, options: skipOption }] };
      }
      education = understood;
    }
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
      return { state: updateDraft(state, {}, "awaiting_project"), messages: [{ text: "Add one relevant project using normal text, for example: Sales Dashboard, built a Power BI dashboard for weekly reporting. Type Skip to omit it.", options: skipOption }] };
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
    if (isSkip(value)) return { state: updateDraft({ ...state, pendingProjectText: undefined }, {}, "awaiting_linkedin"), messages: [{ text: "Please provide your LinkedIn profile URL, or type Skip.", options: skipOption }] };
    if (value === CONFIRM_PROJECT && state.pendingProjectText) return handleResumeBuilderStep({ ...state, pendingProjectText: undefined }, user, `${CONFIRM_PROJECT}:${state.pendingProjectText}`);
    const confirmed = value.startsWith(`${CONFIRM_PROJECT}:`);
    if (!confirmed) {
      const request = projectOrRequest(state, value);
      if (request) return request;
    }
    value = confirmed ? value.slice(CONFIRM_PROJECT.length + 1) : value;
    const projects = clean(value).split(/\s*;\s*/).filter(Boolean).map((raw) => {
      const projectFields = splitFields(raw, 2);
      const commaFields = raw.match(/^([^,\n]{2,100}),\s*(.{3,})$/);
      if (commaFields) return { title: clean(commaFields[1]), description: clean(commaFields[2]) };
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
          text: "Add another project using normal text, for example: Customer Churn Model, built an XGBoost model with 91% accuracy. Short details are also welcome.",
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
    if (value === CONFIRM_PROJECT && state.pendingProjectText) return handleResumeBuilderStep({ ...state, pendingProjectText: undefined }, user, `${CONFIRM_PROJECT}:${state.pendingProjectText}`);
    const confirmed = value.startsWith(`${CONFIRM_PROJECT}:`);
    if (!confirmed) {
      const request = projectOrRequest(state, value);
      if (request) return request;
    }
    value = confirmed ? value.slice(CONFIRM_PROJECT.length + 1) : value;
    const projects = clean(value).split(/\s*;\s*/).filter(Boolean).map((raw) => {
      const projectFields = splitFields(raw, 2);
      const commaFields = raw.match(/^([^,\n]{2,100}),\s*(.{3,})$/);
      if (commaFields) return { title: clean(commaFields[1]), description: clean(commaFields[2]) };
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
          text: "Add another project using normal text, for example: Sales Dashboard, built a Power BI dashboard that improved weekly reporting. Adding 2+ projects significantly improves your ATS score.",
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
  return { state, messages: [{ text: "Choose how you'd like to start.", options: choices }] };
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

/** LinkedIn's own "Get a copy of your data" export -- a ZIP of CSVs the member downloads
 * themselves (Settings & Privacy > Data privacy). Legitimate real LinkedIn content: no
 * scraping, no third-party data broker, nothing beyond what LinkedIn itself hands the
 * member. Structured data already, so (unlike a plain resume upload) it skips straight
 * to creating the resume rather than asking for a target role first. */
async function processLinkedInExportFile(state: ResumeBuilderFlowState, user: User, file: File): Promise<ResumeBuilderFlowResult> {
  try {
    const { input, counts } = await parseLinkedInExport(file);
    if (!counts.experience && !counts.education && !counts.skills && !counts.certifications && !input.summary) {
      throw new Error("That didn't look like a LinkedIn data export — it's the ZIP from Settings & Privacy → Data privacy → Get a copy of your data.");
    }
    const targetRole = input.target_role || state.draft?.targetRole || "";
    const created = await createResume(user.id, {
      title: input.title || "My Resume",
      target_role: targetRole,
      experience_level: "experienced",
      summary: input.summary || "",
      personal_info: { name: user.name, email: user.email, phone: user.mobile },
      skills: input.skills || [],
      experience: input.experience || [],
      education: input.education || [],
      projects: [],
      certifications: input.certifications || [],
    });
    const id = Number(created.id);
    let finalScore = 0;
    let analysis: Record<string, unknown> | undefined;
    try {
      const reanalysis = await analyzeSavedResume(user.id, id, "", targetRole);
      analysis = reanalysis as Record<string, unknown>;
      const scoreNum = Number((reanalysis.score as { normalized_score?: number })?.normalized_score);
      if (Number.isFinite(scoreNum)) finalScore = scoreNum;
    } catch {
      // The import itself succeeded; a transient scoring failure shouldn't block it.
    }
    const title = String(created.title || targetRole || "My Resume");
    return {
      state: { ...state, step: "reviewing", resumeId: id, resumeTitle: title, atsScore: finalScore, draft: { ...state.draft, targetRole, title } },
      messages: [buildAtsScorecardMessage(file.name, targetRole, finalScore, analysis, undefined, false)],
    };
  } catch (error) {
    return {
      state: { ...state, step: "error", error: (error as Error).message },
      messages: [{
        text: `I could not read that LinkedIn export: ${(error as Error).message}`,
        options: [
          { label: "Try again", value: "retry_upload", description: "Attach another LinkedIn export ZIP." },
          { label: "Create a resume", value: "create_resume", description: "Create your resume step-by-step." },
        ],
      }],
    };
  }
}

export async function importResumeBuilderFile(state: ResumeBuilderFlowState, user: User, file: File): Promise<ResumeBuilderFlowResult> {
  if (file.name.toLowerCase().endsWith(".zip")) return processLinkedInExportFile(state, user, file);
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

