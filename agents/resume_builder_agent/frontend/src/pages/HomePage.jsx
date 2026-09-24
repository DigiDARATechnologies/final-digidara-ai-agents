import { useState } from "react";
import { createResume } from "../api/resumes.js";
import ResumeDocument from "../components/ResumeDocument.jsx";
import { TEMPLATE_REGISTRY } from "../components/templates/resumeSchema.js";
import { useNavigate } from "../router.jsx";

const sampleResume = {
  title: "Operations Analyst",
  target_role: "Operations Analyst | Process Improvement | Reporting",
  template_choice: "steady-form",
  personal_info: {
    name: "Avery Stone",
    email: "avery@example.com",
    phone: "+1 555 0198",
    location: "Chicago, IL",
    links: ["LinkedIn: linkedin.com/in/averystone", "Portfolio: averystone.dev"],
  },
  summary:
    "Operations analyst with experience turning messy workflows into measurable, documented systems.",
  education: [
    {
      school: "Northfield University",
      degree: "B.S.",
      field: "Business Analytics",
      end_date: "2025",
    },
  ],
  skills: [
    { skill_name: "SQL, Excel, Power BI" },
    { skill_name: "Process mapping, KPI reporting" },
    { skill_name: "Stakeholder communication" },
  ],
  experience: [
    {
      role: "Operations Analyst Intern",
      company: "Civic Systems",
      start_date: "2025",
      end_date: "Present",
      raw_input:
        "Built weekly reporting dashboards and documented operational handoffs for cross-functional teams.",
      ai_generated_bullets: [
        "Built weekly reporting dashboards that clarified operational handoffs and reduced manual status follow-up.",
      ],
    },
  ],
  projects: [
    {
      title: "Service Desk Trend Review",
      description: "Analyzed request categories, cycle times, and resolution notes to recommend workflow improvements.",
    },
  ],
  declaration:
    "I hereby declare that the information provided in this resume is true and accurate to the best of my knowledge and belief.",
};

const featureLedger = [
  ["Import", "Bring in PDF, DOCX, DOC, or TXT resumes and review extracted content before using it."],
  ["Review", "Use AI suggestions as editable evidence, not black-box rewrites. You approve every line."],
  ["Verify", "Run deterministic ATS checks against resume structure and job-description keywords."],
  ["Export", "Download a selectable-text PDF that matches the chosen preview and A4 layout."],
];

const processSteps = [
  ["01", "Choose or Import", "Open a clean dossier or import an existing resume into the guided editor."],
  ["02", "Add Your Record", "Fill profile, education, experience, skills, projects, certifications, and language sections."],
  ["03", "Improve and Customize", "Tailor wording, review AI suggestions, and switch templates without losing data."],
  ["04", "Check and Export", "Run ATS review, confirm the exact PDF preview, and download the final document."],
];

const checklist = [
  "Contact fields detected",
  "Section headings parse cleanly",
  "Keyword match can use job text",
  "PDF remains selectable text",
];

export default function HomePage() {
  const navigate = useNavigate();
  const [selectedTemplateId, setSelectedTemplateId] = useState("steady-form");
  const [experienceLevel, setExperienceLevel] = useState("fresher");
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const selectedTemplate = TEMPLATE_REGISTRY.find((template) => template.id === selectedTemplateId);

  async function startDossier(templateId = selectedTemplateId) {
    setIsCreating(true);
    setCreateError("");
    try {
      const created = await createResume("Untitled Resume", templateId, experienceLevel);
      navigate(`/resume/${created.id}`);
    } catch (error) {
      setCreateError(error.message || "Could not open a dossier. Confirm the backend is running and try again.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div className="home-page dossier-page">
      <section className="dossier-hero">
        <div className="dossier-hero__copy">
          <p className="dossier-eyebrow">Case file, not a canvas</p>
          <h1>A resume built like it has to survive review.</h1>
          <p>
            ResumeForge AI turns resume building into a structured dossier:
            guided editing, reviewable AI writing, deterministic ATS checks,
            and recruiter-ready PDF export from the same source of truth.
          </p>
          <div className="dossier-actions">
            <button
              className="primary-link"
              disabled={isCreating}
              onClick={() => startDossier()}
              type="button"
            >
              {isCreating ? "Opening..." : "Start Your Dossier"}
            </button>
            <a className="secondary-button" href="#ats-review">See the ATS Review</a>
          </div>
          <fieldset className="dossier-experience-level">
            <legend>Are you a fresher or an experienced professional?</legend>
            <label><input checked={experienceLevel === "fresher"} name="experience-level" onChange={() => setExperienceLevel("fresher")} type="radio" /> Fresher — no work experience yet</label>
            <label><input checked={experienceLevel === "experienced"} name="experience-level" onChange={() => setExperienceLevel("experienced")} type="radio" /> Experienced professional</label>
          </fieldset>
          {createError && <p className="dossier-error" role="status">{createError}</p>}
        </div>

        <div className="dossier-hero__visual" aria-label="Resume dossier preview">
          <div className="dossier-document">
            <div className="dossier-document__scan" aria-hidden="true" />
            <div className="dossier-document__header">
              <span>RF-ATS-042</span>
              <strong>{selectedTemplate?.name}</strong>
            </div>
            <div className="dossier-document__name">Avery Stone</div>
            <div className="dossier-document__rule" />
            <div className="dossier-document__line wide" />
            <div className="dossier-document__line" />
            <div className="dossier-document__line short" />
            <div className="dossier-document__section">Experience</div>
            <div className="dossier-document__line wide" />
            <div className="dossier-document__line" />
          </div>

          <aside className="ats-dossier-card" id="ats-review">
            <p className="dossier-kicker">ATS Review</p>
            <h2>Checklist before export</h2>
            <ul>
              {checklist.map((item) => (
                <li key={item}><span aria-hidden="true">✓</span>{item}</li>
              ))}
            </ul>
          </aside>
        </div>

        <div className="dossier-stats" aria-label="ResumeForge product facts">
          <div><strong>4</strong><span>active templates</span></div>
          <div><strong>Autosave</strong><span>draft protection</span></div>
          <div><strong>ATS</strong><span>category breakdown</span></div>
        </div>
      </section>

      <section className="feature-ledger" aria-label="ResumeForge feature ledger">
        {featureLedger.map(([title, copy]) => (
          <article key={title}>
            <span>{title}</span>
            <p>{copy}</p>
          </article>
        ))}
      </section>

      <section className="dossier-templates" id="templates">
        <div className="dossier-section-heading">
          <p className="dossier-eyebrow">Template archive</p>
          <h2>Four real templates, one structured resume record.</h2>
          <p>Select a template preview below, then open a dossier with that exact template choice.</p>
        </div>

        <div className="dossier-template-grid">
          {TEMPLATE_REGISTRY.map((template) => (
            <article
              className={selectedTemplateId === template.id ? "dossier-template-card selected" : "dossier-template-card"}
              key={template.id}
            >
              <div className="dossier-template-preview" aria-hidden="true">
                <div className="dossier-template-scale">
                  <ResumeDocument
                    resumeData={{ ...sampleResume, template_choice: template.id }}
                    templateId={template.id}
                  />
                </div>
              </div>
              <div className="dossier-template-card__body">
                <span>{template.category}</span>
                <h3>{template.name}</h3>
                <p>{template.description}</p>
              </div>
              <div className="dossier-template-actions">
                <button
                  className="secondary-button"
                  onClick={() => setSelectedTemplateId(template.id)}
                  type="button"
                >
                  Preview
                </button>
                <button
                  className="primary-link"
                  disabled={isCreating}
                  onClick={() => startDossier(template.id)}
                  type="button"
                >
                  Use Template
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="dossier-process">
        <div className="dossier-section-heading">
          <p className="dossier-eyebrow">Process</p>
          <h2>Build the record in four deliberate passes.</h2>
        </div>
        <div className="dossier-process-grid">
          {processSteps.map(([number, title, copy]) => (
            <article key={title}>
              <span>{number}</span>
              <h3>{title}</h3>
              <p>{copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="dossier-final-cta">
        <p className="dossier-eyebrow">Ready when you are</p>
        <h2>Open a dossier and see your first ATS score in minutes.</h2>
        <button
          className="primary-link"
          disabled={isCreating}
          onClick={() => startDossier()}
          type="button"
        >
          Start Your Dossier
        </button>
      </section>
    </div>
  );
}
