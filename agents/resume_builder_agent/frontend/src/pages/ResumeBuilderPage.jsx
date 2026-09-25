import { useEffect, useReducer, useRef, useState } from "react";

import { useLocation, useNavigate, useParams } from "../router.jsx";
import {
  analyzeResumeImport,
  analyzeSavedResume,
  exportResumePdf,
  fetchResume,
  generateExperienceBullets,
  generateProjectBullets,
  generateResumeSummary,
  optimizeResumeWithAi,
  saveResume,
  uploadResumePhoto,
  tailorResumeToJobDescription,
} from "../api/resumes.js";

import { BulletEditor, SkillManager, SuggestionPanel } from "../components/ContentTools.jsx";
import ResumePreview from "../components/ResumePreview.jsx";
import TemplateSwitcher from "../components/TemplateSwitcher.jsx";
import { TEMPLATE_REGISTRY as TEMPLATE_CATALOG } from "../components/templates/resumeSchema.js";
import { cleanBulletText, normalizeBulletList } from "../utils/resumeContent.js";

const PDF_PLACEHOLDER_PATTERN =
  /\[(?:\s*add\b|kpi\s*\d|team\/stakeholders|saved\s+x|business\s+area\/domain)[^\]]*\]/i;

/** Recursively strip bracketed placeholder strings so they never block download */
function stripPdfPlaceholders(value) {
  if (typeof value === "string") {
    return PDF_PLACEHOLDER_PATTERN.test(value) ? "" : value;
  }
  if (Array.isArray(value)) {
    return value
      .map(stripPdfPlaceholders)
      .filter((item) => item !== "" && item !== null && item !== undefined);
  }
  if (value && typeof value === "object") {
    const result = {};
    for (const [key, item] of Object.entries(value)) {
      result[key] = stripPdfPlaceholders(item);
    }
    return result;
  }
  return value;
}


const steps = [
  { label: "Personal Info", tab: "TAB 01" },
  { label: "Education", tab: "TAB 02" },
  { label: "Experience", tab: "TAB 03" },
  { label: "Projects", tab: "TAB 04" },
  { label: "Skills", tab: "TAB 05" },
  { label: "Certifications", tab: "TAB 06" },
  { label: "Publications", tab: "TAB 07" },
  { label: "Languages", tab: "TAB 08" },
  { label: "Achievements", tab: "TAB 09" },
  { label: "Summary", tab: "TAB 10" },
  { label: "Declaration", tab: "TAB 11" },
  { label: "Review", tab: "TAB 12" },
];

const fresherSteps = [
  ...steps.map((step) => step.label === "Experience" ? { ...step, optional: true } : step),
];

const DEFAULT_DECLARATION =
  "I hereby declare that the information provided in this resume is true and accurate to the best of my knowledge and belief.";

function findPdfPlaceholders(value, path = "resume", matches = []) {
  if (typeof value === "string") {
    if (PDF_PLACEHOLDER_PATTERN.test(value)) {
      matches.push(path);
    }
    return matches;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => findPdfPlaceholders(item, `${path}[${index}]`, matches));
    return matches;
  }
  if (value && typeof value === "object") {
    Object.entries(value).forEach(([key, item]) =>
      findPdfPlaceholders(item, `${path}.${key}`, matches),
    );
  }
  return matches;
}

const emptyResume = {
  user_id: "",
  title: "Untitled Resume",
  target_role: "",
  template_choice: "steady-form",
  status: "draft",
  experience_level: null,
  summary: "",
  declaration: DEFAULT_DECLARATION,
  declaration_enabled: true,
  personal_info: {
    name: "",
    email: "",
    phone: "",
    location: "",
    links: [],
  },
  education: [],
  experience: [],
  skills: [],
  certifications: [],
  projects: [],
  publications: [],
  languages: [],
  achievements: [],
};

// Keep the editor in sync with the template gallery. The former small,
// hard-coded allow-list silently changed most selected templates back to
// Precision ATS when a resume was loaded or saved.
const templateChoices = new Set(TEMPLATE_CATALOG.map((template) => template.id));

const legacyTemplateChoices = {
  ats: "steady-form",
  "ats-classic": "steady-form",
  "ats-prime": "steady-form",
  clearpath: "steady-form",
  "essential-one": "steady-form",
  "simple-standard": "steady-form",
  "precision-line": "steady-form",
  "clean-career": "steady-form",
  "graduate-launch": "steady-form",
  "first-career": "steady-form",
  "engineering-core": "steady-form",
  "academic-scholar": "classic-serif",
  "research-profile": "classic-serif",
  classic: "classic-serif",
  "traditional-professional": "classic-serif",
  "classic-clear": "mercury-flow",
  "professional-edge": "mercury-flow",
  "executive-center": "mercury-flow",
  "business-profile": "mercury-flow",
  "consulting-standard": "mercury-flow",
  "finance-formal": "mercury-flow",
  "leadership-profile": "slate-dawn",
  "executive-line": "slate-dawn",
  "executive-sidebar": "slate-dawn",
  "senior-impact": "slate-dawn",
  "two-page-pro": "slate-dawn",
  modern: "mercury-flow",
  "modern-slate": "slate-dawn",
  "urban-teal": "mercury-flow",
  "horizon-blue": "slate-dawn",
  "contemporary-grid": "mercury-flow",
  "analyst-pro": "steady-form",
  "modern-sidebar-pro": "slate-dawn",
  "tech-horizon": "steady-form",
  "product-builder": "steady-form",
  "creative-accent": "mercury-flow",
  "photo-signature": "mercury-flow",
  "designer-portfolio": "slate-dawn",
  "modern-sidebar": "slate-dawn",
  compact: "classic-serif",
  "compact-metrics": "steady-form",
  "compact-career": "classic-serif",
  datacraft: "steady-form",
  "ai-specialist": "steady-form",
  "minimal-focus": "classic-serif",
  "cobalt-line": "slate-dawn",
  "professional-teal": "mercury-flow",
  "data-analyst-pro": "steady-form",
  "corporate-blue": "slate-dawn",
  default: "steady-form",
};

function resumeReducer(state, action) {
  switch (action.type) {
    case "load":
      return normalizeResume(action.payload);
    case "set_field":
      return { ...state, [action.field]: action.value };
    case "set_personal":
      return {
        ...state,
        personal_info: { ...state.personal_info, [action.field]: action.value },
      };
    case "set_profile_link":
      {
        const profileLinks = parseProfileLinks(state.personal_info.links);
        profileLinks[action.linkType] = action.value;
        return {
          ...state,
          personal_info: {
            ...state.personal_info,
            links: serializeProfileLinks(profileLinks),
          },
        };
      }
    case "add_item":
      return { ...state, [action.section]: [...state[action.section], action.item] };
    case "update_item":
      return {
        ...state,
        [action.section]: state[action.section].map((item, index) =>
          index === action.index ? { ...item, [action.field]: action.value } : item,
        ),
      };
    case "remove_item":
      return {
        ...state,
        [action.section]: state[action.section].filter(
          (_item, index) => index !== action.index,
        ),
      };
    default:
      return state;
  }
}

function normalizeResume(resume) {
  const rawTemplateChoice = String(resume.template_choice || "").toLowerCase();
  const templateChoice = templateChoices.has(rawTemplateChoice)
    ? rawTemplateChoice
    : legacyTemplateChoices[rawTemplateChoice] || "steady-form";

  return {
    ...emptyResume,
    ...resume,
    title: resume.title ?? "",
    target_role: resume.target_role ?? "",
    status: resume.status ?? "draft",
    summary: resume.summary ?? "",
    declaration:
      resume.declaration !== undefined && resume.declaration !== null
        ? String(resume.declaration)
        : DEFAULT_DECLARATION,
    declaration_enabled:
      resume.declaration_enabled !== undefined
        ? Boolean(resume.declaration_enabled)
        : resume.declaration !== null && resume.declaration !== undefined
        ? Boolean(String(resume.declaration).trim())
        : true,
    template_choice: templateChoice,
    personal_info: {
      ...emptyResume.personal_info,
      ...(resume.personal_info ?? {}),
      name: resume.personal_info?.name ?? "",
      email: resume.personal_info?.email ?? "",
      phone: resume.personal_info?.phone ?? "",
      location: resume.personal_info?.location ?? "",
      links: resume.personal_info?.links ?? [],
    },
    education: resume.education ?? [],
    experience: (resume.experience ?? []).map((item) => ({
      ...item,
      ai_generated_bullets: Array.isArray(item.ai_generated_bullets)
        ? item.ai_generated_bullets
        : [],
    })),
    skills: resume.skills ?? [],
    certifications: resume.certifications ?? [],
    projects: resume.projects ?? [],
    publications: resume.publications ?? [],
    languages: resume.languages ?? [],
    achievements: resume.achievements ?? [],
  };
}

function draftFingerprint(resume) {
  return JSON.stringify({
    title: resume.title,
    target_role: resume.target_role,
    template_choice: resume.template_choice,
    status: resume.status,
    summary: resume.summary,
    declaration: resume.declaration,
    declaration_enabled: resume.declaration_enabled,
    personal_info: resume.personal_info,
    education: resume.education,
    experience: resume.experience,
    skills: resume.skills,
    certifications: resume.certifications,
    projects: resume.projects,
    publications: resume.publications,
    languages: resume.languages,
    achievements: resume.achievements,
  });
}

function parseProfileLinks(links = []) {
  const values = { github: "", linkedin: "", portfolio: "" };

  for (const link of Array.isArray(links) ? links : []) {
    const value = String(link || "").trim();
    if (!value) {
      continue;
    }

    if (/^(github\s*:|https?:\/\/(?:www\.)?github\.com)/i.test(value)) {
      values.github = value.replace(/^github\s*:\s*/i, "");
    } else if (
      /^(linkedin\s*:|https?:\/\/(?:www\.)?linkedin\.com)/i.test(value)
    ) {
      values.linkedin = value.replace(/^linkedin\s*:\s*/i, "");
    } else if (!values.portfolio) {
      values.portfolio = value.replace(/^(portfolio|website)\s*:\s*/i, "");
    }
  }

  return values;
}

function serializeProfileLinks({ github, linkedin, portfolio }) {
  return [
    github.trim() && `GitHub: ${github.trim()}`,
    linkedin.trim() && `LinkedIn: ${linkedin.trim()}`,
    portfolio.trim() && `Portfolio: ${portfolio.trim()}`,
  ].filter(Boolean);
}

function normalizeDateText(value) {
  const trimmed = value.trim();
  const isoMatch = trimmed.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (isoMatch) {
    const [, year, month, day] = isoMatch;
    return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  }

  const slashMatch = trimmed.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (slashMatch) {
    const [, month, day, year] = slashMatch;
    return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  }

  return trimmed;
}

function normalizeYearText(value) {
  const match = value.trim().match(/\d{4}/);
  return match ? match[0] : value.trim();
}

const blankItems = {
  education: {
    school: "",
    degree: "",
    field: "",
    start_date: "",
    end_date: "",
    cgpa: "",
  },
  experience: {
    company: "",
    role: "",
    start_date: "",
    end_date: "",
    raw_input: "",
    ai_generated_bullets: [],
  },
  skills: { skill_name: "" },
  certifications: { name: "", issuer: "", date: "" },
  projects: { title: "", description: "" },
  publications: { title: "", description: "", date: "" },
  languages: { language_name: "", proficiency: "" },
  achievements: { title: "", description: "", date: "" },
};

export default function ResumeBuilderPage() {
  const { resumeId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const initialUploadedResumeText = location.state?.uploadedResumeText ?? "";
  const initialUploadedFileName = location.state?.uploadedFileName ?? "";
  const aiGeneration = location.state?.aiGeneration;
  const [activeStep, setActiveStep] = useState(
    initialUploadedResumeText ? steps.length - 1 : 0,
  );
  const [resume, dispatch] = useReducer(resumeReducer, emptyResume);
  const [status, setStatus] = useState({ type: "idle", message: "" });
  const [autosaveStatus, setAutosaveStatus] = useState("Loading securely…");
  const lastSavedFingerprint = useRef("");
  const autosaveTimer = useRef(null);
  const [notFound, setNotFound] = useState(false);
  const builderSteps = resume.experience_level === "fresher" ? fresherSteps : steps;
  useEffect(() => {
    let ignore = false;

    async function loadResume() {
      setStatus({ type: "loading", message: "Loading resume..." });
      try {
        const data = await fetchResume(resumeId);
        if (!ignore) {
          lastSavedFingerprint.current = draftFingerprint(normalizeResume(data));
          dispatch({ type: "load", payload: data });
          setAutosaveStatus("All changes saved");
          setNotFound(false);
          setStatus({ type: "idle", message: "" });
        }
      } catch (error) {
        if (!ignore) {
          setNotFound(error.status === 404);
          setStatus({
            type: "error",
            message:
              error.status === 404
                ? "Resume not found. Create a new resume from the dashboard."
                : error.message,
          });
        }
      }
    }

    loadResume();
    return () => {
      ignore = true;
    };
  }, [resumeId]);

  useEffect(() => {
    if (!resume.id) return undefined;
    const fingerprint = draftFingerprint(resume);
    if (fingerprint === lastSavedFingerprint.current) return undefined;

    window.clearTimeout(autosaveTimer.current);
    setAutosaveStatus("Unsaved changes");
    autosaveTimer.current = window.setTimeout(async () => {
      setAutosaveStatus("Saving…");
      try {
        await saveResume(resumeId, resume);
        lastSavedFingerprint.current = fingerprint;
        setAutosaveStatus("All changes saved");
      } catch {
        setAutosaveStatus("Autosave paused — use Save");
      }
    }, 1200);
    return () => window.clearTimeout(autosaveTimer.current);
  }, [resume, resumeId]);

  async function handleSave() {
    setStatus({ type: "loading", message: "Saving..." });
    try {
      const saved = await saveResume(resumeId, resume);
      lastSavedFingerprint.current = draftFingerprint(normalizeResume(saved));
      dispatch({ type: "load", payload: saved });
      if (String(saved.id) !== String(resumeId)) {
        navigate(`/resume/${saved.id}`, { replace: true });
      }
      setStatus({ type: "success", message: "Saved successfully." });
    } catch (error) {
      setStatus({ type: "error", message: error.message });
    }
  }

  async function handleTemplateChange(templateChoice) {
    const nextResume = { ...resume, template_choice: templateChoice };
    dispatch({
      type: "set_field",
      field: "template_choice",
      value: templateChoice,
    });
    setStatus({ type: "loading", message: "Saving template..." });

    try {
      const saved = await saveResume(resumeId, nextResume);
      dispatch({ type: "load", payload: saved });
      if (String(saved.id) !== String(resumeId)) {
        navigate(`/resume/${saved.id}`, { replace: true });
      }
      setStatus({ type: "success", message: "Template updated." });
    } catch (error) {
      setStatus({ type: "error", message: error.message });
    }
  }

  async function handleDownloadPdf() {
    const cleanedResume = stripPdfPlaceholders(resume);
    setStatus({ type: "loading", message: "Preparing exact PDF…" });

    try {
      const saved = await saveResume(resumeId, cleanedResume);
      dispatch({ type: "load", payload: saved });
      if (String(saved.id) !== String(resumeId)) {
        navigate(`/resume/${saved.id}`, { replace: true });
      }
      const { blob, filename } = await exportResumePdf(
        saved.id,
        saved.template_choice,
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      // Revoke on the next tick, not synchronously — some browsers haven't
      // finished reading the blob into the download yet, which corrupts
      // or truncates the saved PDF if the object URL dies too early.
      window.setTimeout(() => URL.revokeObjectURL(url), 4000);
      setStatus({ type: "success", message: "✅ PDF downloaded successfully!" });
    } catch (error) {
      setStatus({ type: "error", message: error.message });
    }
  }

  const isFirstStep = activeStep === 0;

  const isLastStep = activeStep === steps.length - 1;
  const isBusy = status.type === "loading";
  const progress = calculateResumeProgress(resume);

  if (notFound) {
    return (
      <section className="not-found-state">
        <p className="eyebrow">Resume not found</p>
        <h1>This resume is unavailable.</h1>
        <p>Create a new resume from the dashboard or open one you own.</p>
        <button
          className="primary-link"
          onClick={() => navigate("/resumes")}
          type="button"
        >
          Back to dashboard
        </button>
      </section>
    );
  }

  return (
    <div className="builder-page">
      <aside className="stepper" aria-label="Resume form steps">
        {builderSteps.map((step, index) => (
          <button
            className={index === activeStep ? "step active" : "step"}
            key={step.label}
            onClick={() => setActiveStep(index)}
            type="button"
          >
            <span>{step.tab}</span>
            {step.label}{step.optional ? " (optional)" : ""}
          </button>
        ))}
      </aside>

      <section className="editor-panel">
        <div className="editor-header">
          <div className="editor-header__top">
            <div className="editor-header__title">
              <p className="eyebrow">Resume #{resumeId}</p>
              <h1>{builderSteps[activeStep].label}{builderSteps[activeStep].optional ? " (optional)" : ""}</h1>
            </div>
            <div className="editor-header__progress" aria-label={`Resume completion ${progress}%`}>
              <span>{progress}% complete</span>
              <small className="autosave-state">{autosaveStatus}</small>
              <div className="editor-header__progress-bar">
                <div className="editor-header__progress-bar-fill" style={{ width: `${progress}%` }} />
              </div>
            </div>
          </div>
          <div className="editor-actions">
            <TemplateSwitcher
              onChange={handleTemplateChange}
              resume={resume}
              value={resume.template_choice}
            />
            <button
              className="save-button"
              disabled={isBusy}
              onClick={handleSave}
              type="button"
            >
              Save
            </button>
            <button
              className="download-button"
              disabled={isBusy}
              onClick={handleDownloadPdf}
              type="button"
            >
              Download PDF
            </button>
          </div>
        </div>

        <div className="editor-body">
          <label>
            Resume title
            <input
              value={resume.title}
              onChange={(event) =>
                dispatch({
                  type: "set_field",
                  field: "title",
                  value: event.target.value,
                })
              }
            />
          </label>

          <label>
            Target job title
            <input
              placeholder="Data Analyst, Software Engineer, Product Manager..."
              value={resume.target_role}
              onChange={(event) =>
                dispatch({
                  type: "set_field",
                  field: "target_role",
                  value: event.target.value,
                })
              }
            />
          </label>

          {status.message && (
            <p className={`status-message ${status.type}`}>{status.message}</p>
          )}

          {aiGeneration && (
            <AiGenerationStatus
              generated={aiGeneration.generated ?? {}}
              resume={resume}
              roleAlignment={aiGeneration.roleAlignment}
              skipped={aiGeneration.skipped ?? []}
            />
          )}

          <StepContent
            activeStep={activeStep}
            stepList={builderSteps}
            dispatch={dispatch}
            initialUploadedFileName={initialUploadedFileName}
            initialUploadedResumeText={initialUploadedResumeText}
            resume={resume}
          />

          <div className="form-actions">
            <button
              className="secondary-button"
              disabled={isFirstStep}
              onClick={() => setActiveStep((step) => step - 1)}
              type="button"
            >
              ← Back
            </button>
            <button
              className="primary-link"
              disabled={isLastStep}
              onClick={() => setActiveStep((step) => step + 1)}
              type="button"
            >
              Next Step →
            </button>
          </div>
        </div>
      </section>

      <ResumePreview resume={resume} />
    </div>
  );
}

function AiGenerationStatus({ generated, resume, skipped, roleAlignment }) {
  const skippedExperience = skipped.filter((entry) => entry.section === "experience").length;
  const skippedProjects = skipped.filter((entry) => entry.section === "projects").length;
  const generatedExperience = Number.isInteger(generated.experience)
    ? generated.experience
    : Math.max(0, (resume.experience?.length ?? 0) - skippedExperience);
  const generatedProjects = Number.isInteger(generated.projects)
    ? generated.projects
    : Math.max(0, (resume.projects?.length ?? 0) - skippedProjects);
  const generatedAchievements = Number.isInteger(generated.achievements)
    ? generated.achievements
    : 0;
  const generatedParts = [
    generated.summary ? "summary" : null,
    generated.skills > 0 ? `${generated.skills} skills` : null,
    generated.education > 0 ? `${generated.education} education ${generated.education === 1 ? "entry" : "entries"} retained` : null,
    generated.certifications > 0 ? `${generated.certifications} certification ${generated.certifications === 1 ? "entry" : "entries"} retained` : null,
    generatedExperience > 0 ? `${generatedExperience} experience ${generatedExperience === 1 ? "entry" : "entries"}` : null,
    generatedProjects > 0 ? `${generatedProjects} project ${generatedProjects === 1 ? "entry" : "entries"}` : null,
    generatedAchievements > 0 ? `${generatedAchievements} achievement ${generatedAchievements === 1 ? "entry" : "entries"}` : null,
    generated.declaration ? "declaration" : null,
  ].filter(Boolean);
  const absentSections = [
    generated.skills === 0 ? "skills" : null,
    generated.education === 0 ? "education" : null,
    generated.certifications === 0 ? "certifications" : null,
  ].filter(Boolean);
  const retainedEntries = skipped.filter((entry) => entry.reason?.includes("original uploaded text was retained")).length;
  const missingSourceEntries = skipped.length - retainedEntries;
  const skippedMessages = [
    retainedEntries
      ? ` ${retainedEntries} ${retainedEntries === 1 ? "entry was" : "entries were"} retained because the AI response did not include usable rewritten bullets.`
      : "",
    missingSourceEntries
      ? ` ${missingSourceEntries} ${missingSourceEntries === 1 ? "entry was" : "entries were"} skipped because no usable source content was found.`
      : "",
  ].filter(Boolean);
  const skippedText = skippedMessages.length ? skippedMessages.join("") : " No entries were skipped.";
  const completedText = generatedParts.length
    ? `AI prepared your ${generatedParts.join(", ")}.`
    : "AI prepared the available uploaded content.";
  const absentText = absentSections.length
    ? ` No ${absentSections.join(", ")} were detected in the uploaded resume, so they were left blank instead of being invented.`
    : "";
  return <>
    <p className="status-message success">{completedText}{absentText}{skippedText}</p>
    {roleAlignment?.level !== "direct" && roleAlignment?.message && (
      <p className="status-message warning">Target-role evidence: {roleAlignment.message}</p>
    )}
  </>;
}

function StepContent({
  activeStep,
  dispatch,
  initialUploadedFileName,
  initialUploadedResumeText,
  resume,
  stepList,
}) {
  switch (stepList[activeStep]?.label || stepList[activeStep]) {
    case "Personal Info":
      return <PersonalInfoStep dispatch={dispatch} resume={resume} />;
    case "Education":
      return (
        <CollectionStep
          addLabel="Add education"
          dispatch={dispatch}
          fields={[
            ["school", "School"],
            ["degree", "Degree"],
            ["field", "Field"],
            ["start_date", "Start year"],
            ["end_date", "End year"],
            ["cgpa", "CGPA"],
          ]}
          section="education"
          values={resume.education}
        />
      );
    case "Experience":
      return <ExperienceStep dispatch={dispatch} experienceLevel={resume.experience_level} optional={resume.experience_level === "fresher"} values={resume.experience} />;
    case "Projects":
      return <CollectionStep addLabel="Add project" dispatch={dispatch} fields={[["title", "Project title"], ["description", "Project details"]]} section="projects" values={resume.projects} />;
    case "Skills":
      return (
        <SkillManager
          onChange={(skills) =>
            dispatch({ type: "set_field", field: "skills", value: skills })
          }
          skills={resume.skills}
        />
      );
    case "Certifications":
      return (
        <CollectionStep
          addLabel="Add certification"
          dispatch={dispatch}
          fields={[
            ["name", "Name"],
            ["issuer", "Issuer"],
            ["date", "Date"],
          ]}
          section="certifications"
          values={resume.certifications}
        />
      );
    case "Publications":
      return (
        <CollectionStep
          addLabel="Add publication"
          dispatch={dispatch}
          fields={[
            ["title", "Title"],
            ["description", "Publication details"],
            ["date", "Date"],
          ]}
          section="publications"
          values={resume.publications}
        />
      );
    case "Languages":
      return (
        <CollectionStep
          addLabel="Add language"
          dispatch={dispatch}
          fields={[
            ["language_name", "Language"],
            ["proficiency", "Proficiency"],
          ]}
          section="languages"
          values={resume.languages}
        />
      );
    case "Achievements":
      return (
        <CollectionStep
          addLabel="Add achievement"
          dispatch={dispatch}
          fields={[
            ["title", "Title"],
            ["description", "Description"],
            ["date", "Date"],
          ]}
          section="achievements"
          values={resume.achievements}
        />
      );
    case "Summary":
      return <SummaryStep dispatch={dispatch} resume={resume} />;
    case "Declaration":
      return <DeclarationStep dispatch={dispatch} resume={resume} />;
    default:
      return (
        <ReviewStep
          dispatch={dispatch}
          initialUploadedFileName={initialUploadedFileName}
          initialUploadedResumeText={initialUploadedResumeText}
          resume={resume}
        />
      );
  }
}

function PersonalInfoStep({ dispatch, resume }) {
  const info = resume.personal_info;
  const profileLinks = parseProfileLinks(info.links);
  return (
    <div className="form-grid">
      {[
        ["name", "Name"],
        ["email", "Email"],
        ["phone", "Phone"],
        ["location", "Location"],
      ].map(([field, label]) => (
        <label key={field}>
          {label}
          <input
            value={info[field]}
            onChange={(event) =>
              dispatch({
                type: "set_personal",
                field,
                value: event.target.value,
              })
            }
          />
        </label>
      ))}
      <label>
        GitHub
        <input
          inputMode="url"
          onChange={(event) =>
            dispatch({
              type: "set_profile_link",
              linkType: "github",
              value: event.target.value,
            })
          }
          placeholder="https://github.com/username"
          type="url"
          value={profileLinks.github}
        />
      </label>
      <label>
        LinkedIn
        <input
          inputMode="url"
          onChange={(event) =>
            dispatch({
              type: "set_profile_link",
              linkType: "linkedin",
              value: event.target.value,
            })
          }
          placeholder="https://linkedin.com/in/username"
          type="url"
          value={profileLinks.linkedin}
        />
      </label>
      <label className="full-width">
        <span>
          Portfolio <span className="optional-label">(optional)</span>
        </span>
        <input
          inputMode="url"
          onChange={(event) =>
            dispatch({
              type: "set_profile_link",
              linkType: "portfolio",
              value: event.target.value,
            })
          }
          placeholder="https://yourportfolio.com"
          type="url"
          value={profileLinks.portfolio}
        />
      </label>
      <label className="full-width">
        Profile photo <span className="optional-label">(Navy Portrait only)</span>
        <input
          accept="image/png,image/jpeg,image/webp"
          onChange={async (event) => {
            const file = event.target.files?.[0];
            if (!file || !resume.id) return;
            try {
              const updated = await uploadResumePhoto(resume.id, file);
              dispatch({ type: "load", payload: updated });
            } catch (error) {
              window.alert(error.message || "Unable to upload profile photo.");
            } finally {
              event.target.value = "";
            }
          }}
          type="file"
        />
      </label>
    </div>
  );
}

function DateInput({ onChange, value }) {
  const normalizedValue = /^\d{4}-\d{2}-\d{2}$/.test(value ?? "") ? value : "";
  return (
    <input
      className="calendar-date-input"
      onChange={(event) => onChange(event.target.value)}
      title="Choose a calendar date."
      type="date"
      value={normalizedValue}
    />
  );
}

function YearInput({ onChange, value }) {
  const year = normalizeYearText(String(value ?? ""));
  const normalizedValue = /^\d{4}$/.test(year) ? `${year}-01-01` : "";

  return (
    <input
      className="calendar-date-input"
      onChange={(event) => onChange(event.target.value.slice(0, 4))}
      title="Choose a calendar date. Only the year is saved."
      type="date"
      value={normalizedValue}
    />
  );
}

function DecimalInput({ onChange, value }) {
  return (
    <input
      inputMode="decimal"
      onChange={(event) => {
        const nextValue = event.target.value.replace(/[^\d.]/g, "");
        const normalizedValue = nextValue
          .replace(/^(\d*\.?\d*).*$/, "$1")
          .replace(/(\..*)\./g, "$1");
        onChange(normalizedValue);
      }}
      pattern="\\d+(\\.\\d+)?"
      placeholder="0.00"
      title="Enter decimal numbers only, for example 8.75."
      type="text"
      value={value ?? ""}
    />
  );
}

function CollectionStep({ addLabel, dispatch, fields, section, values }) {
  return (
    <div className="collection">
      {values.map((item, index) => (
        <div className="collection-item" key={`${section}-${index}`}>
          <div className="collection-header">
            <h2>{item.title || item.role || item.school || item.name || addLabel}</h2>
            <button
              onClick={() => dispatch({ type: "remove_item", section, index })}
              type="button"
            >
              Remove
            </button>
          </div>
          <div className="form-grid">
            {fields.map(([field, label]) => (
              <label
                className={[
                  field.includes("input") || field === "description" ? "full-width" : "",
                  section === "skills" ? "bullet-field" : "",
                ].filter(Boolean).join(" ")}
                key={field}
              >
                {label}
                {field.includes("input") || field === "description" ? (
                  <textarea
                    rows="4"
                    value={item[field] ?? ""}
                    onChange={(event) =>
                      dispatch({
                        type: "update_item",
                        section,
                        index,
                        field,
                        value: event.target.value,
                      })
                    }
                  />
                ) : section === "education" && field.includes("date") ? (
                  <YearInput
                    value={item[field] ?? ""}
                    onChange={(value) =>
                      dispatch({
                        type: "update_item",
                        section,
                        index,
                        field,
                        value,
                      })
                    }
                  />
                ) : section === "education" && field === "cgpa" ? (
                  <DecimalInput
                    value={item[field] ?? ""}
                    onChange={(value) =>
                      dispatch({
                        type: "update_item",
                        section,
                        index,
                        field,
                        value,
                      })
                    }
                  />
                ) : field.includes("date") ? (
                  <DateInput
                    value={item[field] ?? ""}
                    onChange={(value) =>
                      dispatch({
                        type: "update_item",
                        section,
                        index,
                        field,
                        value,
                      })
                    }
                  />
                ) : (
                  <span className={section === "skills" ? "bullet-input-wrap" : ""}>
                    {section === "skills" && <span className="bullet-mark" aria-hidden="true">•</span>}
                    <input
                      type="text"
                      value={item[field] ?? ""}
                      onChange={(event) =>
                        dispatch({
                          type: "update_item",
                          section,
                          index,
                          field,
                          value: event.target.value,
                        })
                      }
                    />
                  </span>
                )}
              </label>
            ))}
          </div>
        </div>
      ))}
      <button
        className="secondary-button"
        onClick={() =>
          dispatch({ type: "add_item", section, item: { ...blankItems[section] } })
        }
        type="button"
      >
        {addLabel}
      </button>
    </div>
  );
}

function ExperienceStep({ dispatch, experienceLevel, optional = false, values }) {
  const [industry, setIndustry] = useState("");
  const [aiDrafts, setAiDrafts] = useState({});

  async function handleImprove(index, item) {
    setAiDrafts((drafts) => ({
      ...drafts,
      [index]: {
        bullets: [],
        error: "",
        loading: true,
      },
    }));

    try {
      const data = await generateExperienceBullets({
        rawInput: item.raw_input,
        role: item.role,
        industry: industry || "General",
        experienceLevel,
      });
      setAiDrafts((drafts) => ({
        ...drafts,
        [index]: {
          bullets: data.bullets.map((bullet) => ({
            accepted: true,
            text: bullet,
          })),
          error: "",
          loading: false,
        },
      }));
    } catch (error) {
      setAiDrafts((drafts) => ({
        ...drafts,
        [index]: {
          bullets: [],
          error: error.message,
          loading: false,
        },
      }));
    }
  }

  function updateDraftBullet(index, bulletIndex, updates) {
    setAiDrafts((drafts) => ({
      ...drafts,
      [index]: {
        ...drafts[index],
        bullets: drafts[index].bullets.map((bullet, currentIndex) =>
          currentIndex === bulletIndex ? { ...bullet, ...updates } : bullet,
        ),
      },
    }));
  }

  function rejectDraftBullet(index, bulletIndex) {
    setAiDrafts((drafts) => ({
      ...drafts,
      [index]: {
        ...drafts[index],
        bullets: drafts[index].bullets.filter(
          (_bullet, currentIndex) => currentIndex !== bulletIndex,
        ),
      },
    }));
  }

  function acceptSelectedBullets(index) {
    const selectedBullets = (aiDrafts[index]?.bullets ?? [])
      .filter((bullet) => bullet.accepted && bullet.text.trim())
      .map((bullet) => cleanBulletText(bullet.text));

    dispatch({
      type: "update_item",
      section: "experience",
      index,
      field: "ai_generated_bullets",
      value: selectedBullets,
    });
  }

  return (
    <div className="collection">
      {optional && <p className="status-message info">Optional for freshers. Add internships, part-time roles, or volunteer experience only when you have them.</p>}
      <label>
        Industry context
        <input
          onChange={(event) => setIndustry(event.target.value)}
          placeholder="SaaS, healthcare, finance..."
          value={industry}
        />
      </label>

      {values.map((item, index) => {
        const draft = aiDrafts[index];
        const canImprove = item.raw_input?.trim() && item.role?.trim();

        return (
          <div className="collection-item" key={`experience-${index}`}>
            <div className="collection-header">
              <h2>{item.role || item.company || "Add experience"}</h2>
              <button
                onClick={() =>
                  dispatch({ type: "remove_item", section: "experience", index })
                }
                type="button"
              >
                Remove
              </button>
            </div>

            <div className="form-grid">
              {[
                ["company", "Company"],
                ["role", "Role"],
                ["start_date", "Start date"],
                ["end_date", "End date"],
              ].map(([field, label]) => (
                <label key={field}>
                  {label}
                  {field.includes("date") ? (
                    <DateInput
                      onChange={(value) =>
                        dispatch({
                          type: "update_item",
                          section: "experience",
                          index,
                          field,
                          value,
                        })
                      }
                      value={item[field] ?? ""}
                    />
                  ) : (
                    <input
                      onChange={(event) =>
                        dispatch({
                          type: "update_item",
                          section: "experience",
                          index,
                          field,
                          value: event.target.value,
                        })
                      }
                      type="text"
                      value={item[field] ?? ""}
                    />
                  )}
                </label>
              ))}

              <label className="full-width checkbox-field">
                <span>
                  <input
                    checked={Boolean(item.is_current)}
                    onChange={(event) =>
                      dispatch({
                        type: "update_item",
                        section: "experience",
                        index,
                        field: "is_current",
                        value: event.target.checked,
                      })
                    }
                    type="checkbox"
                  />
                  I currently work in this role
                </span>
              </label>

              <label className="full-width">
                <span className="field-label-row">
                  <span className="bullet-label"><span aria-hidden="true">•</span> Raw input</span>
                  <button
                    className="ai-button"
                    disabled={!canImprove || draft?.loading}
                    onClick={() => handleImprove(index, item)}
                    type="button"
                  >
                    {draft?.loading ? "Improving..." : "Improve with AI"}
                  </button>
                </span>
                <textarea
                  className="raw-input-textarea"
                  onChange={(event) =>
                    dispatch({
                      type: "update_item",
                      section: "experience",
                      index,
                      field: "raw_input",
                      value: event.target.value,
                    })
                  }
                  rows="4"
                  value={item.raw_input ?? ""}
                />
              </label>
            </div>

            {draft?.error && <p className="ai-error">{draft.error}</p>}

            {draft?.bullets?.length > 0 && (
              <div className="ai-bullets-panel">
                <div className="ai-bullets-header">
                  <h3>Review generated bullets</h3>
                  <button
                    className="secondary-button"
                    onClick={() => acceptSelectedBullets(index)}
                    type="button"
                  >
                    Use selected
                  </button>
                </div>

                {draft.bullets.map((bullet, bulletIndex) => (
                  <div className="ai-bullet-row" key={`ai-${index}-${bulletIndex}`}>
                    <input
                      checked={bullet.accepted}
                      onChange={(event) =>
                        updateDraftBullet(index, bulletIndex, {
                          accepted: event.target.checked,
                        })
                      }
                      type="checkbox"
                    />
                    <textarea
                      onChange={(event) =>
                        updateDraftBullet(index, bulletIndex, {
                          text: event.target.value,
                        })
                      }
                      rows="2"
                      value={bullet.text}
                    />
                    <button
                      onClick={() => rejectDraftBullet(index, bulletIndex)}
                      type="button"
                    >
                      Reject
                    </button>
                  </div>
                ))}
              </div>
            )}

            {item.ai_generated_bullets?.length > 0 && (
              <BulletEditor
                bullets={item.ai_generated_bullets}
                onChange={(bullets) =>
                  dispatch({
                    type: "update_item",
                    section: "experience",
                    index,
                    field: "ai_generated_bullets",
                    value: bullets,
                  })
                }
                title="Approved experience bullets"
              />
            )}

            {!item.ai_generated_bullets?.length && (
              <BulletEditor
                bullets={[]}
                onChange={(bullets) =>
                  dispatch({
                    type: "update_item",
                    section: "experience",
                    index,
                    field: "ai_generated_bullets",
                    value: bullets,
                  })
                }
                title="Approved experience bullets"
              />
            )}
          </div>
        );
      })}

      <button
        className="secondary-button"
        onClick={() =>
          dispatch({
            type: "add_item",
            section: "experience",
            item: { ...blankItems.experience },
          })
        }
        type="button"
      >
        Add experience
      </button>
    </div>
  );
}

function ProjectStep({ dispatch, values }) {
  const [drafts, setDrafts] = useState({});

  async function handleGenerate(index, item) {
    setDrafts((current) => ({
      ...current,
      [index]: { error: "", loading: true, suggestions: [] },
    }));

    try {
      const data = await generateProjectBullets({
        rawInput: item.description,
        title: item.title,
        technologies: "",
      });
      setDrafts((current) => ({
        ...current,
        [index]: {
          error: "",
          loading: false,
          suggestions: data.bullets.map((bullet) => ({
            content: cleanBulletText(bullet),
            reason: "Saved as a project bullet in the existing description field.",
          })),
        },
      }));
    } catch (error) {
      setDrafts((current) => ({
        ...current,
        [index]: { error: error.message, loading: false, suggestions: [] },
      }));
    }
  }

  function projectBullets(item) {
    return normalizeBulletList(String(item.description || "").split("\n"));
  }

  function setProjectBullets(index, bullets) {
    dispatch({
      type: "update_item",
      section: "projects",
      index,
      field: "description",
      value: normalizeBulletList(bullets).join("\n"),
    });
  }

  return (
    <div className="collection">
      {values.map((item, index) => {
        const draft = drafts[index] || {};
        const canGenerate = item.description?.trim()?.length >= 20;

        return (
          <div className="collection-item" key={`project-${index}`}>
            <div className="collection-header">
              <h2>{item.title || "Add project"}</h2>
              <button
                onClick={() => dispatch({ type: "remove_item", section: "projects", index })}
                type="button"
              >
                Remove
              </button>
            </div>

            <div className="form-grid">
              <label>
                Title
                <input
                  onChange={(event) =>
                    dispatch({
                      type: "update_item",
                      section: "projects",
                      index,
                      field: "title",
                      value: event.target.value,
                    })
                  }
                  value={item.title ?? ""}
                />
              </label>

              <label className="full-width">
                <span className="field-label-row">
                  <span className="bullet-label"><span aria-hidden="true">&bull;</span> Raw input</span>
                  <button
                    className="ai-button"
                    disabled={!canGenerate || draft.loading}
                    onClick={() => handleGenerate(index, item)}
                    type="button"
                  >
                    {draft.loading ? "Generating..." : "Generate bullets"}
                  </button>
                </span>
                <textarea
                  className="raw-input-textarea"
                  onChange={(event) =>
                    dispatch({
                      type: "update_item",
                      section: "projects",
                      index,
                      field: "description",
                      value: event.target.value,
                    })
                  }
                  placeholder="Paste rough project notes, tools, scope, and verified outcomes."
                  rows="5"
                  value={item.description ?? ""}
                />
              </label>
            </div>

            <SuggestionPanel
              error={draft.error}
              loading={draft.loading}
              onApply={(value) => setProjectBullets(index, [...projectBullets(item), value])}
              onRegenerate={() => handleGenerate(index, item)}
              onReject={(suggestionIndex) =>
                setDrafts((current) => ({
                  ...current,
                  [index]: {
                    ...draft,
                    suggestions: draft.suggestions.filter((_item, currentIndex) => currentIndex !== suggestionIndex),
                  },
                }))
              }
              suggestions={draft.suggestions || []}
              title="Review project bullets"
            />

            <BulletEditor
              bullets={projectBullets(item)}
              onChange={(bullets) => setProjectBullets(index, bullets)}
              title="Approved project bullets"
            />
          </div>
        );
      })}

      <button
        className="secondary-button"
        onClick={() =>
          dispatch({
            type: "add_item",
            section: "projects",
            item: { ...blankItems.projects },
          })
        }
        type="button"
      >
        Add project
      </button>
    </div>
  );
}

function SummaryStep({ dispatch, resume }) {
  const [targetRole, setTargetRole] = useState(resume.target_role ?? "");
  const summaryRequestRef = useRef(0);
  const [draft, setDraft] = useState({
    accepted: true,
    error: "",
    loading: false,
    note: "",
    summary: "",
  });

  useEffect(() => {
    setTargetRole(resume.target_role ?? "");
  }, [resume.target_role]);

  useEffect(() => {
    setDraft((current) => (
      current.summary
        ? { accepted: true, error: "", loading: false, note: "", summary: "" }
        : current
    ));
  }, [targetRole]);

  async function handleGenerateSummary() {
    const requestedRole = targetRole.trim();
    const requestId = summaryRequestRef.current + 1;
    summaryRequestRef.current = requestId;
    setDraft({
      accepted: true,
      error: "",
      loading: true,
      note: "",
      summary: "",
    });

    try {
      const data = await generateResumeSummary({
        jobDescription: resume.job_description ?? "",
        resume: {
          ...resume,
          target_role: requestedRole,
        },
        targetRole: requestedRole,
      });
      if (requestId !== summaryRequestRef.current) {
        return;
      }
      setDraft({
        accepted: true,
        error: "",
        loading: false,
        note: data.note ?? "",
        summary: data.summary,
      });
    } catch (error) {
      if (requestId !== summaryRequestRef.current) {
        return;
      }
      setDraft({
        accepted: true,
        error: error.message,
        loading: false,
        note: "",
        summary: "",
      });
    }
  }

  function acceptSummary() {
    if (!draft.accepted || !draft.summary.trim()) {
      return;
    }

    const acceptedRole = targetRole.trim();
    if (acceptedRole) {
      dispatch({
        type: "set_field",
        field: "target_role",
        value: acceptedRole,
      });
    }

    dispatch({
      type: "set_field",
      field: "summary",
      value: draft.summary.trim(),
    });
  }

  function rejectSummary() {
    setDraft({
      accepted: true,
      error: "",
      loading: false,
      note: "",
      summary: "",
    });
  }

  return (
    <div className="summary-step">
      <div className="form-grid">
        <label>
          Target role
          <input
            onChange={(event) => setTargetRole(event.target.value)}
            placeholder="Product Manager, Data Analyst..."
            value={targetRole}
          />
        </label>
        <div className="summary-generate-slot">
          <button
            className="ai-button"
            disabled={!targetRole.trim() || draft.loading}
            onClick={handleGenerateSummary}
            type="button"
          >
            {draft.loading ? "Generating..." : "Generate with AI"}
          </button>
        </div>
        <label className="full-width">
          Saved summary
          <textarea
            onChange={(event) =>
              dispatch({
                type: "set_field",
                field: "summary",
                value: event.target.value,
              })
            }
            rows="5"
            value={resume.summary ?? ""}
          />
        </label>
      </div>

      {draft.error && <p className="ai-error">{draft.error}</p>}
      {draft.note && <p className="status-message success">{draft.note}</p>}

      {draft.summary && (
        <div className="ai-bullets-panel summary-review-panel">
          <div className="ai-bullets-header">
            <h3>Review generated summary</h3>
            <button
              className="secondary-button"
              disabled={!draft.accepted}
              onClick={acceptSummary}
              type="button"
            >
              Use selected
            </button>
          </div>

          <div className="ai-bullet-row summary-review-row">
            <input
              checked={draft.accepted}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  accepted: event.target.checked,
                }))
              }
              type="checkbox"
            />
            <textarea
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  summary: event.target.value,
                }))
              }
              rows="4"
              value={draft.summary}
            />
            <button onClick={rejectSummary} type="button">
              Reject
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function DeclarationStep({ dispatch, resume }) {
  const defaultDeclaration = DEFAULT_DECLARATION;
  const isEnabled = resume.declaration_enabled !== false;

  const currentDeclaration =
    resume.declaration !== undefined ? resume.declaration : defaultDeclaration;

  return (
    <div className="declaration-step">
      <div className="form-grid">
        <label className="full-width checkbox-field" style={{ marginBottom: "14px" }}>
          <span>
            <input
              checked={isEnabled}
              onChange={(event) => {
                const nextEnabled = event.target.checked;
                dispatch({
                  type: "set_field",
                  field: "declaration_enabled",
                  value: nextEnabled,
                });
                if (nextEnabled && !resume.declaration?.trim()) {
                  dispatch({
                    type: "set_field",
                    field: "declaration",
                    value: defaultDeclaration,
                  });
                }
              }}
              type="checkbox"
            />
            Include Declaration section in resume
          </span>
        </label>

        {isEnabled && (
          <label className="full-width">
            Declaration statement
            <textarea
              onChange={(event) =>
                dispatch({
                  type: "set_field",
                  field: "declaration",
                  value: event.target.value,
                })
              }
              rows="4"
              placeholder={DEFAULT_DECLARATION}
              value={currentDeclaration}
            />
          </label>
        )}
      </div>
      {isEnabled && (
        <div style={{ display: "flex", gap: "10px", marginTop: "14px" }}>
          <button
            className="secondary-button"
            onClick={() =>
              dispatch({
                type: "set_field",
                field: "declaration",
                value: defaultDeclaration,
              })
            }
            type="button"
          >
            Reset to default
          </button>
          <button
            className="danger-button"
            onClick={() =>
              dispatch({
                type: "set_field",
                field: "declaration",
                value: "",
              })
            }
            type="button"
          >
            Clear declaration
          </button>
        </div>
      )}
    </div>
  );
}

function ReviewStep({
  dispatch,
  initialUploadedFileName = "",
  initialUploadedResumeText = "",
  resume,
}) {
  const [jobDescription, setJobDescription] = useState("");
  const [selectedFile, setSelectedFile] = useState(
    initialUploadedFileName ? { name: initialUploadedFileName, size: 0 } : null
  );
  const [uploadedResumeText, setUploadedResumeText] = useState(
    initialUploadedResumeText,
  );
  const [uploadedAnalysis, setUploadedAnalysis] = useState(null);
  const [currentAnalysis, setCurrentAnalysis] = useState(null);
  const [isAnalyzingCurrent, setIsAnalyzingCurrent] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progressText, setProgressText] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [tailorState, setTailorState] = useState({
    error: "",
    loading: false,
    note: "",
    reworded_bullets: [],
    suggested_keywords: [],
  });
  const optimizeRequestInFlightRef = useRef(false);

  const ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx", ".txt"];
  const MAX_FILE_BYTES = 5 * 1024 * 1024; // 5 MB

  function validateFile(file) {
    if (!file) return "No file selected.";
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return "Unsupported format. Upload a PDF, Word (.doc or .docx), or TXT resume.";
    }
    if (file.size > MAX_FILE_BYTES) {
      return "Resume file must be 5 MB or smaller.";
    }
    if (file.size === 0) {
      return "The uploaded resume is empty.";
    }
    return null;
  }

  async function processSelectedFile(file) {
    setUploadError("");
    const errorMsg = validateFile(file);
    if (errorMsg) {
      setUploadError(errorMsg);
      return;
    }

    setSelectedFile(file);
    setIsProcessing(true);
    try {
      setProgressText("Validating resume…");
      const result = await analyzeResumeImport({ file, jobDescription, targetRole: resume.target_role ?? "" });
      if (result?.extractedText && result?.atsAnalysis) {
        setProgressText("Analyzing ATS compatibility…");
        setUploadedResumeText(result.extractedText);
        setUploadedAnalysis(result.atsAnalysis);
      } else {
        throw new Error("Could not extract and analyze the resume.");
      }
      setProgressText("");
    } catch (err) {
      setUploadedResumeText("");
      setUploadedAnalysis(null);
      setUploadError(err.message || "Failed to process resume file.");
      setProgressText("");
    } finally {
      setIsProcessing(false);
    }
  }

  function handleFileInputChange(e) {
    const file = e.target.files?.[0];
    if (file) {
      processSelectedFile(file);
    }
  }

  function handleDragOver(e) {
    e.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave(e) {
    e.preventDefault();
    setIsDragging(false);
  }

  function handleDrop(e) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      processSelectedFile(file);
    }
  }

  function handleRemoveFile() {
    setSelectedFile(null);
    setUploadedResumeText("");
    setUploadedAnalysis(null);
    setUploadError("");
    setProgressText("");
  }

  function handleClearAll() {
    handleRemoveFile();
    setJobDescription("");
    setTailorState({
      error: "",
      loading: false,
      note: "",
      reworded_bullets: [],
      suggested_keywords: [],
    });
  }

  async function handleAnalyzeClick() {
    if (!selectedFile) {
      setUploadError("Please choose a resume file to analyze.");
      return;
    }
    await processSelectedFile(selectedFile);
  }

  async function handleTailorResume() {
    if (!jobDescription.trim()) {
      setTailorState({
        error: "Paste a target job description first, then run Tailor My Resume.",
        loading: false,
        note: "",
        reworded_bullets: [],
        suggested_keywords: [],
      });
      document.getElementById("atsJobDescription")?.focus();
      return;
    }

    setTailorState({
      error: "",
      loading: true,
      note: "",
      reworded_bullets: [],
      suggested_keywords: [],
    });

    try {
      const data = await tailorResumeToJobDescription({
        resume,
        jobDescription,
      });
      setTailorState({
        error: "",
        loading: false,
        note: data.note ?? "",
        reworded_bullets: data.reworded_bullets ?? [],
        suggested_keywords: data.suggested_keywords ?? [],
      });
    } catch (error) {
      setTailorState({
        error: error.message,
        loading: false,
        note: "",
        reworded_bullets: [],
        suggested_keywords: [],
      });
    }
  }

  async function handleAnalyzeCurrentResume() {
    setIsAnalyzingCurrent(true);
    setUploadError("");
    try {
      await saveResume(resume.id, resume);
      const analysis = await analyzeSavedResume(resume.id, jobDescription, resume.target_role ?? "");
      setCurrentAnalysis(analysis);
    } catch (error) {
      setUploadError(error.message || "Could not analyze the current resume.");
    } finally {
      setIsAnalyzingCurrent(false);
    }
  }

  async function handleApplyAtsFixes() {
    if (optimizeRequestInFlightRef.current) return;
    if (!resume.target_role?.trim()) {
      setTailorState((current) => ({
        ...current,
        error: "Add a target role above first, then run Apply ATS Fixes.",
        note: "",
      }));
      return;
    }

    optimizeRequestInFlightRef.current = true;
    setTailorState((current) => ({
      ...current,
      error: "",
      loading: true,
      note: "",
    }));

    try {
      const data = await optimizeResumeWithAi({
        resume,
        targetRole: resume.target_role,
        jobDescription,
      });
      dispatch({ type: "load", payload: { ...resume, ...data.resume } });
      setTailorState((current) => ({
        ...current,
        error: "",
        loading: false,
        note: "AI-generated ATS fixes applied. Review the updated summary and bullets before final use.",
      }));
    } catch (error) {
      setTailorState((current) => ({
        ...current,
        error: error.message || "Could not generate AI-optimized resume content.",
        loading: false,
        note: "",
      }));
    } finally {
      optimizeRequestInFlightRef.current = false;
    }
  }

  function getFileExtLabel(name) {
    if (!name) return "FILE";
    const ext = name.substring(name.lastIndexOf(".")).toUpperCase().replace(".", "");
    return ext || "FILE";
  }

  function getFileTypeLabel(name) {
    if (!name) return "Document";
    const ext = name.substring(name.lastIndexOf(".")).toLowerCase();
    if (ext === ".pdf") return "PDF Document";
    if (ext === ".docx" || ext === ".doc") return "Word Document";
    if (ext === ".txt") return "Text Document";
    return "Document";
  }

  function formatFileSize(bytes) {
    if (!bytes || isNaN(bytes)) return "0 KB";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  const hasTailoringResults =
    tailorState.suggested_keywords.length > 0 ||
    tailorState.reworded_bullets.length > 0;
  const activeAnalysis = uploadedAnalysis || currentAnalysis;
  const generatedContent = buildGeneratedContentIdeas(resume, jobDescription);

  return (
    <section className="review-panel">
      <header className="review-panel__header">
        <div>
          <p className="eyebrow">FINAL REVIEW & OPTIMIZATION</p>
          <h2>Resume Review & ATS Check</h2>
          <p>Review your resume details, upload an existing resume to run an ATS check, and tailor keywords for target roles.</p>
        </div>
      </header>

      <div className="review-panel__body">
        <section className="ats-check-card">
          <div className="ats-check-card__header">
            <p className="ats-check-card__eyebrow eyebrow">UPLOAD ATS CHECK</p>
            <h2 className="ats-check-card__title">Check an existing resume</h2>
            <p className="ats-check-card__description">
              Upload your PDF, Word or TXT resume and compare it with a target job description to identify ATS improvements.
            </p>
          </div>

          {!selectedFile ? (
            <div
              className={`resume-upload ${isDragging ? "is-dragging" : ""}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <input
                id="atsResumeUpload"
                className="visually-hidden"
                type="file"
                accept=".pdf,.doc,.docx,.txt,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                onChange={handleFileInputChange}
                disabled={isProcessing}
              />
              <label htmlFor="atsResumeUpload" className="resume-upload__label">
                <span className="resume-upload__icon" aria-hidden="true">
                  ↑
                </span>
                <span className="resume-upload__text">
                  <strong>Choose a resume</strong>
                  <span>or drag and drop it here</span>
                </span>
                <span className="resume-upload__formats">
                  PDF, DOC, DOCX or TXT — maximum 5 MB
                </span>
              </label>
            </div>
          ) : (
            <div className="selected-file">
              <div className="selected-file__icon" aria-hidden="true">
                {getFileExtLabel(selectedFile.name)}
              </div>
              <div className="selected-file__details">
                <strong className="selected-file__name" title={selectedFile.name}>
                  {selectedFile.name}
                </strong>
                <span className="selected-file__meta">
                  {formatFileSize(selectedFile.size)} · {getFileTypeLabel(selectedFile.name)}
                </span>
              </div>
              <label htmlFor="atsResumeUploadReplace" className="secondary-button compact-button" style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center' }}>
                Replace
                <input
                  id="atsResumeUploadReplace"
                  className="visually-hidden"
                  type="file"
                  accept=".pdf,.doc,.docx,.txt,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                  onChange={handleFileInputChange}
                  disabled={isProcessing}
                />
              </label>
              <button
                type="button"
                className="danger-button compact-button"
                onClick={handleRemoveFile}
                disabled={isProcessing}
              >
                Remove
              </button>
            </div>
          )}

          <div className="form-message form-message--info">
            <span>Supported formats: PDF, DOC, DOCX and TXT. Scanned PDFs may require OCR and can produce less accurate results.</span>
          </div>

          {progressText && (
            <div className="form-message form-message--info">
              <span>{progressText}</span>
            </div>
          )}

          {uploadError && (
            <div className="form-message form-message--error">
              <span>{uploadError}</span>
            </div>
          )}

          <div className="job-description-group">
            <div className="job-description-header">
              <label htmlFor="atsJobDescription" className="job-description-label">
                Target Job Description
              </label>
              <div className="job-description-meta">
                <span className="char-count">{jobDescription.length} characters</span>
                {jobDescription.length > 0 && (
                  <button
                    type="button"
                    className="text-button compact-button"
                    onClick={() => setJobDescription("")}
                    disabled={isProcessing}
                  >
                    Clear text
                  </button>
                )}
              </div>
            </div>
            <textarea
              id="atsJobDescription"
              className="job-description-textarea"
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Paste the target job description here to compare keywords and role requirements..."
              disabled={isProcessing}
              rows={6}
            />
          </div>

          <div className="ats-check-actions">
            <button
              type="button"
              className="primary-button"
              onClick={handleAnalyzeCurrentResume}
              disabled={isAnalyzingCurrent || isProcessing || !resume.id}
            >
              {isAnalyzingCurrent ? "Checking current draft…" : "Check Current Resume"}
            </button>

            <button
              type="button"
              className="secondary-button"
              onClick={handleAnalyzeClick}
              disabled={!selectedFile || isProcessing}
            >
              {isProcessing ? progressText || "Analyzing..." : "Analyze Uploaded Resume"}
            </button>

            <button
              type="button"
              className="ai-button"
              onClick={handleTailorResume}
              disabled={isProcessing || tailorState.loading}
              title="Paste a target job description to tailor this resume."
            >
              {tailorState.loading ? "Tailoring..." : "Tailor My Resume"}
            </button>

            <button
              type="button"
              className="secondary-button"
              onClick={handleApplyAtsFixes}
              disabled={isProcessing || tailorState.loading}
            >
              {tailorState.loading ? "Applying..." : "Apply ATS Fixes"}
            </button>

            <button
              type="button"
              className="outline-button"
              onClick={handleClearAll}
              disabled={isProcessing || (!selectedFile && !jobDescription && !uploadedResumeText)}
            >
              Clear
            </button>
          </div>

          {tailorState.error && (
            <div className="form-message form-message--error">
              <span>{tailorState.error}</span>
            </div>
          )}
          {tailorState.note && (
            <div className="form-message form-message--info">
              <span>{tailorState.note}</span>
            </div>
          )}
        </section>

        <section className="ats-results">
          {hasTailoringResults && (
            <div className="tailor-results">
              <section>
                <h3>Suggested keywords</h3>
                <div className="keyword-list">
                  {tailorState.suggested_keywords.map((keyword, index) => (
                    <span key={`keyword-${index}`}>{keyword}</span>
                  ))}
                </div>
              </section>

              <section>
                <h3>Reworded bullets</h3>
                <ul>
                  {tailorState.reworded_bullets.map((bullet, index) => (
                    <li key={`reworded-${index}`}>{bullet}</li>
                  ))}
                </ul>
              </section>
            </div>
          )}

          {isProcessing || isAnalyzingCurrent ? (
            <AnalysisSkeleton />
          ) : activeAnalysis ? (
            <AtsAnalysisResult analysis={activeAnalysis} />
          ) : (
            <section className="ats-empty-state">
              <p className="eyebrow">No analysis yet</p>
              <h3>Run a backend check to see deterministic results.</h3>
              <p>Use “Check Current Resume” for a resume-quality score, or paste a job description for an ATS Compatibility Estimate.</p>
            </section>
          )}
          <GeneratedContentPanel items={generatedContent} />
        </section>
      </div>
    </section>
  );
}

function UploadedResumeImprovements({ score }) {
  return (
    <section className="uploaded-improvements-panel">
      <div className="improvements-heading">
        <div>
          <p className="eyebrow">Personalized analysis</p>
          <h2>What to improve</h2>
          <p>Complete the highest-priority changes before submitting your resume.</p>
        </div>
        <strong>{score.improvements.length} actions</strong>
      </div>

      <div className="improvement-list">
        {score.improvements.map((improvement) => (
          <article
            className={`improvement-item priority-${improvement.priority}`}
            key={improvement.title}
          >
            <span>{improvement.priority} priority</span>
            <div>
              <h3>{improvement.title}</h3>
              <p>{improvement.detail}</p>
            </div>
          </article>
        ))}
      </div>

      <div className="analysis-gaps">
        <section>
          <h3>Missing sections</h3>
          {score.missingSections.length ? (
            <div className="keyword-list missing-section-list">
              {score.missingSections.map((section) => (
                <span key={section}>{section}</span>
              ))}
            </div>
          ) : (
            <p>All essential ATS sections were detected.</p>
          )}
        </section>
        <section>
          <h3>Missing job keywords</h3>
          {score.missingKeywords.length ? (
            <div className="keyword-list">
              {score.missingKeywords.map((keyword) => (
                <span key={keyword}>{keyword}</span>
              ))}
            </div>
          ) : (
            <p>
              {score.hasJobDescription
                ? "No major keyword gaps were detected."
                : "Paste a job description to reveal missing keywords."}
            </p>
          )}
        </section>
      </div>
    </section>
  );
}

function AtsAnalysisResult({ analysis }) {
  const score = normalizeAnalysisScore(analysis);
  const breakdown = Object.entries(analysis.breakdown || {});
  const isJobMatch = analysis.analysis_type === "job_match";
  const title = isJobMatch ? "ATS Compatibility Estimate" : "Resume Quality Score";
  const requirements = analysis.requirements || [];
  const recommendations = analysis.recommendations || [];
  const confidenceReasons = analysis.score?.confidence_reasons || [];

  return (
    <section className="ats-analysis-result">
      <div className="ats-score-summary ats-score-overview">
        <div
          className="ats-score-ring"
          style={{ "--score": `${score.normalized}%` }}
          aria-label={`${title} ${score.normalized} percent`}
        >
          <strong>{score.normalized}</strong>
          <span>{title}</span>
        </div>
        <div>
          <p className="eyebrow">{analysis.analysis_type === "job_match" ? "Job match mode" : "Resume-only mode"}</p>
          <h2>{score.classification}</h2>
          <p>{analysis.clarification}</p>
          <dl className="analysis-meta-grid">
            <div><dt>Confidence</dt><dd>{score.confidence}</dd></div>
            <div><dt>Analyzed</dt><dd>{formatAnalysisDate(analysis.metadata?.analyzed_at)}</dd></div>
            <div><dt>Scoring</dt><dd>{analysis.metadata?.scoring_version || "1.0.0"}</dd></div>
          </dl>
          {confidenceReasons.length > 0 && (
            <p className="status-message warning">{score.confidence} confidence: {confidenceReasons.join(" ")}</p>
          )}
        </div>
      </div>

      <div className="ats-breakdown-grid">
        {breakdown.map(([key, item]) => (
          <article className="ats-breakdown-card" key={key}>
            <div className="ats-breakdown-card__header">
              <h3>{item.label || key}</h3>
              <strong>{formatScoreNumber(item.earned)}/{formatScoreNumber(item.maximum)}</strong>
            </div>
            <div className="ats-meter">
              <span style={{ width: `${item.maximum ? Math.round((item.earned / item.maximum) * 100) : 0}%` }} />
            </div>
            <p>{item.explanation}</p>
            {item.improvement_action && <p><strong>Action:</strong> {item.improvement_action}</p>}
          </article>
        ))}
      </div>

      {isJobMatch && <SkillsAnalysis skills={analysis.skills || {}} />}
      {isJobMatch && <RequirementsTable requirements={requirements} />}

      <section className="analysis-section">
        <h3>Formatting analysis</h3>
        {(analysis.formatting_warnings || []).length ? (
          <ul>
            {analysis.formatting_warnings.map((warning, index) => (
              <li key={`format-${index}`}><strong>{warning.severity}:</strong> {warning.problem} {warning.fix}</li>
            ))}
          </ul>
        ) : (
          <p>No critical parsing warnings were detected.</p>
        )}
      </section>

      <section className="analysis-section">
        <h3>Prioritized recommendations</h3>
        {recommendations.length ? (
          <div className="recommendation-grid">
            {recommendations.map((item, index) => (
              <article className="recommendation-card" key={`${item.problem}-${index}`}>
                <span>{item.priority}</span>
                <h4>{item.problem}</h4>
                <p>{item.why_it_matters}</p>
                <p><strong>Fix:</strong> {item.exact_fix}</p>
                <p><strong>Example:</strong> {item.truthful_example}</p>
              </article>
            ))}
          </div>
        ) : (
          <p>No major recommendations were generated.</p>
        )}
      </section>
    </section>
  );
}

function SkillsAnalysis({ skills }) {
  const groups = [
    ["Matched required skills", skills.matched_required || [], "matched"],
    ["Missing required skills", skills.missing_required || [], "missing"],
    ["Matched preferred skills", skills.matched_preferred || [], "matched"],
    ["Missing preferred skills", skills.missing_preferred || [], "missing"],
    ["Additional relevant skills", skills.additional_relevant || [], "neutral"],
  ];
  return (
    <section className="analysis-section">
      <h3>Skills analysis</h3>
      <div className="skills-analysis-grid">
        {groups.map(([label, items, status]) => (
          <div key={label}>
            <h4>{label}</h4>
            <div className="keyword-list">
              {items.length ? items.map((item) => (
                <span className={`skill-status-chip ${status}`} key={item.skill}>{status}: {item.skill}</span>
              )) : <span className="skill-status-chip neutral">None detected</span>}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function RequirementsTable({ requirements }) {
  if (!requirements.length) return null;
  return (
    <section className="analysis-section">
      <h3>Requirement analysis</h3>
      <div className="requirements-table-wrap">
        <table className="requirements-table">
          <thead>
            <tr>
              <th>Job requirement</th>
              <th>Status</th>
              <th>Resume evidence</th>
              <th>Recommendation</th>
            </tr>
          </thead>
          <tbody>
            {requirements.map((item, index) => (
              <tr key={`${item.requirement}-${index}`}>
                <td>{item.requirement}</td>
                <td>{item.status}</td>
                <td>{(item.resume_evidence || []).map((evidence) => `${evidence.section}: ${evidence.text}`).join("; ") || "No evidence found"}</td>
                <td>{item.recommendation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AnalysisSkeleton() {
  return (
    <section className="ats-analysis-result is-loading">
      <div className="analysis-skeleton wide" />
      <div className="analysis-skeleton-grid">
        <div className="analysis-skeleton" />
        <div className="analysis-skeleton" />
        <div className="analysis-skeleton" />
      </div>
    </section>
  );
}

function normalizeAnalysisScore(analysis) {
  const score = analysis.score && typeof analysis.score === "object" ? analysis.score : {};
  const normalized = Number(score.normalized_score ?? analysis.legacyScore ?? analysis.score ?? 0);
  return {
    normalized: Number.isFinite(normalized) ? Math.max(0, Math.min(100, Math.round(normalized))) : 0,
    classification: score.classification || analysis.rating || "Analysis complete",
    confidence: score.confidence || "Medium",
  };
}

function formatAnalysisDate(value) {
  if (!value) return "Just now";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Just now" : date.toLocaleString();
}

function formatScoreNumber(value) {
  const number = Number(value || 0);
  return Number.isInteger(number) ? number : number.toFixed(1);
}

function serverAnalysisToPanel(analysis, hasJobDescription) {
  const recommendations = analysis.recommendations ?? [];
  const criticalIssues = analysis.criticalIssues ?? [];
  const suggestions = [
    ...criticalIssues.map((item) => `${item.section}: ${item.problem}. ${item.whyItMatters}`),
    ...recommendations.map((item) => `${item.section}: ${item.suggestedImprovement}`),
  ];
  const improvements = [
    ...criticalIssues.map((item) => ({
      priority: "high",
      title: item.problem,
      detail: item.whyItMatters,
    })),
    ...recommendations.map((item) => ({
      priority: item.priority === "High" ? "high" : item.priority === "Medium" ? "medium" : "low",
      title: item.problem,
      detail: item.suggestedImprovement,
    })),
  ];
  if (!improvements.length) {
    improvements.push({
      priority: "low",
      title: "Final human review",
      detail: "Verify every claim, metric, date, and keyword before submitting.",
    });
  }
  return {
    total: Number(analysis.score ?? 0),
    label: analysis.rating ?? "ATS review",
    message: `${analysis.summary ?? "Deterministic ATS-readability estimate."} This is guidance, not a score from an employer's ATS.`,
    metrics: (analysis.categories ?? []).map((category) => ({
      label: category.category,
      value: category.maxPoints
        ? Math.round((category.pointsEarned / category.maxPoints) * 100)
        : 0,
    })),
    suggestions: suggestions.length
      ? suggestions.slice(0, 8)
      : ["The key ATS structure checks passed. Tailor wording to the target role."],
    improvements,
    missingSections: criticalIssues
      .filter((item) => /missing/i.test(item.problem))
      .map((item) => item.section),
    missingKeywords: analysis.jobMatch?.missingKeywords?.slice(0, 12) ?? [],
    hasJobDescription,
  };
}

function AtsScorePanel({ score, title = "ATS score review" }) {
  return (
    <section className="ats-score-panel" aria-label={title}>
      <div className="ats-score-summary">
        <div
          className="ats-score-ring"
          style={{ "--score": `${score.total}%` }}
          aria-label={`ATS score ${score.total} percent`}
        >
          <strong>{score.total}</strong>
          <span>ATS score</span>
        </div>
        <div>
          <p className="eyebrow">ATS readiness</p>
          <h2>{title === "ATS score review" ? score.label : title}</h2>
          <p>{score.message}</p>
        </div>
      </div>

      <div className="ats-metrics">
        {score.metrics.map((metric) => (
          <div className="ats-metric" key={metric.label}>
            <div>
              <span>{metric.label}</span>
              <strong>{metric.value}%</strong>
            </div>
            <div className="ats-meter">
              <span style={{ width: `${metric.value}%` }} />
            </div>
          </div>
        ))}
      </div>

      <div className="ats-suggestions">
        <h3>Recommended fixes</h3>
        <ul>
          {score.suggestions.map((suggestion) => (
            <li key={suggestion}>{suggestion}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function GeneratedContentPanel({ items }) {
  return (
    <section className="generated-content-panel">
      <div>
        <p className="eyebrow">AI generated content</p>
        <h2>Suggested resume content</h2>
      </div>
      <div className="generated-content-grid">
        {items.map((item) => (
          <article key={item.title}>
            <h3>{item.title}</h3>
            <p>{item.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function calculateAtsScore(resume, jobDescription) {
  const requiredSections = [
    Boolean(resume.personal_info?.name?.trim()),
    Boolean(resume.personal_info?.email?.trim()),
    Boolean(resume.personal_info?.phone?.trim()),
    Boolean(resume.summary?.trim()),
    resume.education?.length > 0,
    resume.experience?.length > 0,
    resume.skills?.length > 0,
    resume.publications?.length > 0,
  ];
  const completeness = Math.round(
    (requiredSections.filter(Boolean).length / requiredSections.length) * 100,
  );

  const resumeText = [
    resume.title,
    resume.summary,
    resume.personal_info?.location,
    ...(resume.skills ?? []).map((item) => item.skill_name),
    ...(resume.experience ?? []).flatMap((item) => [
      item.company,
      item.role,
      item.raw_input,
      ...(item.ai_generated_bullets ?? []),
    ]),
    ...(resume.education ?? []).flatMap((item) => [
      item.school,
      item.degree,
      item.field,
    ]),
    ...(resume.projects ?? []).flatMap((item) => [item.title, item.description]),
    ...(resume.publications ?? []).flatMap((item) => [item.title, item.description]),
    ...(resume.certifications ?? []).flatMap((item) => [item.name, item.issuer]),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  const jdKeywords = extractKeywords(jobDescription);
  const keywordCoverage =
    jdKeywords.length === 0
      ? 60
      : Math.round(
        (jdKeywords.filter((keyword) => resumeText.includes(keyword)).length /
          jdKeywords.length) *
        100,
      );

  const experienceQuality = Math.min(
    100,
    Math.round(
      ((resume.experience?.length ?? 0) * 22) +
      ((resume.publications?.length ?? 0) * 14) +
      ((resume.skills?.length ?? 0) * 4) +
      ((resume.summary?.trim() ? 18 : 0)),
    ),
  );

  const total = Math.round(
    completeness * 0.4 + keywordCoverage * 0.35 + experienceQuality * 0.25,
  );

  const suggestions = [];
  if (!resume.summary?.trim()) {
    suggestions.push("Add a focused professional summary with target role keywords.");
  }
  if ((resume.skills?.length ?? 0) < 6) {
    suggestions.push("Add more role-specific skills from the job description.");
  }
  if ((resume.experience?.length ?? 0) === 0) {
    suggestions.push("Add at least one experience entry with measurable outcomes.");
  }
  if ((resume.publications?.length ?? 0) === 0) {
    suggestions.push("Add publications to improve proof-of-skill coverage.");
  }
  if (jdKeywords.length === 0) {
    suggestions.push("Paste a job description to calculate keyword match accurately.");
  } else if (keywordCoverage < 70) {
    suggestions.push("Use more matching keywords from the pasted job description.");
  }
  if (suggestions.length === 0) {
    suggestions.push("Strong ATS structure. Review wording and metrics before export.");
  }

  return {
    total,
    label:
      total >= 85
        ? "Strong match"
        : total >= 70
          ? "Good foundation"
          : total >= 50
            ? "Needs optimization"
            : "Incomplete resume",
    message:
      total >= 85
        ? "Your resume has solid structure, keyword coverage, and section depth."
        : "Improve the suggested areas before applying for the best ATS match.",
    metrics: [
      { label: "Completeness", value: completeness },
      { label: "Keyword match", value: keywordCoverage },
      { label: "Experience depth", value: experienceQuality },
    ],
    suggestions,
  };
}

function calculateResumeProgress(resume) {
  const weightedChecks = [
    [8, Boolean(resume.title?.trim() && resume.title !== "Untitled Resume")],
    [8, Boolean(resume.target_role?.trim())],
    [18, Boolean(resume.personal_info?.name?.trim() && resume.personal_info?.email?.trim())],
    [14, Boolean(resume.summary?.trim())],
    [14, (resume.skills?.length ?? 0) > 0],
    [18, (resume.experience?.length ?? 0) > 0],
    [10, (resume.education?.length ?? 0) > 0],
    [6, (resume.publications?.length ?? 0) > 0],
    [2, (resume.certifications?.length ?? 0) > 0],
    [2, (resume.languages?.length ?? 0) > 0],
  ];
  const earned = weightedChecks.reduce((sum, [weight, passed]) => sum + (passed ? weight : 0), 0);
  const total = weightedChecks.reduce((sum, [weight]) => sum + weight, 0);
  return Math.round((earned / total) * 100);
}

function calculateUploadedAtsScore(uploadedText, jobDescription) {
  const text = uploadedText.toLowerCase();
  const jdKeywords = extractKeywords(jobDescription);
  const sectionDefinitions = [
    { label: "Professional summary", terms: ["summary", "profile", "objective"] },
    { label: "Skills", terms: ["skills", "core competencies", "technical skills"] },
    { label: "Experience", terms: ["experience", "employment", "work history"] },
    { label: "Publications", terms: ["publications", "publication", "papers"] },
    { label: "Education", terms: ["education", "academic background"] },
  ];
  const missingSections = sectionDefinitions
    .filter(({ terms }) => !terms.some((term) => text.includes(term)))
    .map(({ label }) => label);
  const detectedSections = sectionDefinitions.length - missingSections.length;
  const keywordCoverage =
    jdKeywords.length === 0
      ? 50
      : Math.round(
        (jdKeywords.filter((keyword) => text.includes(keyword)).length /
          jdKeywords.length) *
        100,
      );
  const completeness = Math.round(
    (detectedSections / sectionDefinitions.length) * 100,
  );
  const actionWords = [
    "built",
    "created",
    "analyzed",
    "improved",
    "reduced",
    "increased",
    "developed",
    "automated",
    "led",
    "delivered",
    "optimized",
    "managed",
  ];
  const matchedActionWords = actionWords.filter((word) => text.includes(word));
  const metricMatches =
    uploadedText.match(
      /\b\d+(?:\.\d+)?%|\b\d+\s*(?:hours|users|records|reports|projects|clients|customers|days|weeks|months)\b/gi,
    ) ?? [];
  const impact = Math.min(
    100,
    Math.round(
      matchedActionWords.length * 7 + Math.min(metricMatches.length * 12, 36),
    ),
  );
  const total = Math.round(completeness * 0.35 + keywordCoverage * 0.4 + impact * 0.25);
  const missingKeywords = jdKeywords
    .filter((keyword) => !text.includes(keyword))
    .slice(0, 10);
  const contactGaps = [
    !/[\w.+-]+@[\w.-]+\.[a-z]{2,}/i.test(uploadedText) && "email",
    !/(?:\+?\d[\d\s().-]{7,}\d)/.test(uploadedText) && "phone number",
    !/(linkedin\.com|github\.com|https?:\/\/)/i.test(uploadedText) &&
    "LinkedIn, portfolio, or GitHub link",
  ].filter(Boolean);
  const wordCount = uploadedText.trim().split(/\s+/).filter(Boolean).length;
  const bulletCount = (uploadedText.match(/^\s*[-*•]\s+/gm) ?? []).length;
  const usesFirstPerson = /\b(i|me|my|mine)\b/i.test(uploadedText);
  const improvements = [];

  if (missingSections.length) {
    improvements.push({
      priority: "high",
      title: "Add missing ATS sections",
      detail: `Use clear headings for ${missingSections.join(", ")} so screening software can classify your information.`,
    });
  }
  if (contactGaps.length) {
    improvements.push({
      priority: "high",
      title: "Complete contact information",
      detail: `Add your ${contactGaps.join(", ")} near the top of the resume.`,
    });
  }
  if (jobDescription.trim() && missingKeywords.length) {
    improvements.push({
      priority: keywordCoverage < 50 ? "high" : "medium",
      title: "Close the keyword gap",
      detail: `Use relevant missing terms naturally in your summary, skills, and achievement bullets: ${missingKeywords.slice(0, 6).join(", ")}.`,
    });
  } else if (!jobDescription.trim()) {
    improvements.push({
      priority: "medium",
      title: "Add the target job description",
      detail: "Paste the job description above to compare role-specific skills, tools, and responsibilities.",
    });
  }
  if (metricMatches.length < 3) {
    improvements.push({
      priority: "high",
      title: "Quantify more achievements",
      detail: "Add numbers to at least three bullets, such as percentages, time saved, revenue, users, reports, or project volume.",
    });
  }
  if (matchedActionWords.length < 4) {
    improvements.push({
      priority: "medium",
      title: "Strengthen bullet openings",
      detail: "Start achievement bullets with varied action verbs such as Led, Built, Improved, Automated, Delivered, or Optimized.",
    });
  }
  if (bulletCount < 3) {
    improvements.push({
      priority: "medium",
      title: "Use concise achievement bullets",
      detail: "Break dense paragraphs into short bullets that show action, task, tools used, and measurable result.",
    });
  }
  if (wordCount < 250 || wordCount > 900) {
    improvements.push({
      priority: "medium",
      title: wordCount < 250 ? "Add more evidence" : "Reduce resume length",
      detail:
        wordCount < 250
          ? `Only ${wordCount} words were detected. Add relevant experience, projects, skills, and measurable outcomes.`
          : `${wordCount} words were detected. Remove repetition and keep only information relevant to the target role.`,
    });
  }
  if (usesFirstPerson) {
    improvements.push({
      priority: "low",
      title: "Remove first-person wording",
      detail: 'Delete words such as "I", "me", and "my"; resume bullets should begin directly with an action verb.',
    });
  }
  if (improvements.length === 0) {
    improvements.push({
      priority: "low",
      title: "Perform a final relevance check",
      detail: "The structure is strong. Verify every bullet supports the target role and uses accurate metrics.",
    });
  }
  const suggestions = improvements
    .slice(0, 5)
    .map((improvement) => improvement.detail);

  return {
    total,
    label: total >= 75 ? "Uploaded resume is close" : "Uploaded resume needs work",
    message: "This score is based on headings, keyword coverage, and measurable impact in the uploaded text.",
    metrics: [
      { label: "Section structure", value: completeness },
      { label: "Keyword match", value: keywordCoverage },
      { label: "Impact wording", value: impact },
    ],
    hasJobDescription: Boolean(jobDescription.trim()),
    improvements,
    missingKeywords,
    missingSections,
    suggestions,
  };
}

function buildGeneratedContentIdeas(resume, jobDescription) {
  const keywords = extractKeywords(jobDescription).slice(0, 6);
  const role = resume.title || "Target Role";
  const keywordText = keywords.length ? keywords.join(", ") : "role-specific tools and measurable outcomes";

  return [
    {
      title: "Professional summary",
      body: `${role} candidate with hands-on experience in ${keywordText}. Skilled at translating business needs into clear deliverables, improving workflows, and communicating insights to stakeholders.`,
    },
    {
      title: "Achievement bullet",
      body: `Improved reporting efficiency by building reusable dashboards and analysis workflows using ${keywordText}, reducing manual follow-up and helping teams make faster decisions.`,
    },
    {
      title: "Project description",
      body: `Designed an end-to-end project using ${keywordText}; cleaned source data, created structured outputs, documented assumptions, and presented recommendations with clear business impact.`,
    },
  ];
}

function extractKeywords(value) {
  const stopWords = new Set([
    "and",
    "the",
    "for",
    "with",
    "you",
    "our",
    "are",
    "will",
    "from",
    "that",
    "this",
    "have",
    "has",
    "your",
    "role",
    "work",
    "team",
    "job",
    "candidate",
  ]);

  return Array.from(
    new Set(
      value
        .toLowerCase()
        .match(/[a-z][a-z+#.]{2,}/g)
        ?.filter((word) => !stopWords.has(word))
        .slice(0, 28) ?? [],
    ),
  );
}
