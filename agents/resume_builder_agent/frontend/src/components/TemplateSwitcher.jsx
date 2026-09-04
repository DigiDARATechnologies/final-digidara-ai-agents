import { useEffect, useMemo, useState } from "react";
import { listTemplates, previewResumePdf } from "../api/resumes.js";
import { TEMPLATE_REGISTRY } from "./templates/resumeSchema.js";

const TEMPLATE_SAMPLE_RESUME = {
  title: "Data Analyst",
  target_role: "DATA ANALYST | SQL | PYTHON | POWER BI",
  template_choice: "steady-form",
  personal_info: {
    name: "Alex Morgan",
    email: "alex@example.com",
    phone: "+91 98765 43210",
    location: "Tamil Nadu, India",
    links: [
      "LinkedIn: linkedin.com/in/alexmorgan",
      "GitHub: github.com/alexmorgan",
      "Portfolio: alexmorgan.dev",
    ],
  },
  summary: "Data analyst experienced in transforming business data into actionable insights.",
  education: [
    {
      school: "Example University",
      degree: "Master of Computer Applications",
      field: "Computer Applications",
      end_date: "2026",
    },
  ],
  skills: [
    { skill_name: "Programming: Python, SQL" },
    { skill_name: "BI Tools: Power BI, Excel, Tableau" },
    { skill_name: "Data Analytics: EDA, Data Cleaning, KPI Reporting" },
    { skill_name: "Machine Learning: Regression, Classification" },
  ],
  experience: [
    {
      role: "Data Analyst Intern",
      company: "Technology Company",
      start_date: "2025",
      end_date: "Present",
      ai_generated_bullets: ["Built dashboards for weekly business reporting."],
    },
  ],
  projects: [
    {
      title: "Sales Analytics Dashboard",
      description: "Technologies: Power BI, SQL\nImproved sales visibility for regional leaders.",
    },
  ],
  certifications: [
    {
      name: "Data Analytics Certification",
      issuer: "Professional Academy",
      date: "2025",
    },
  ],
};

const fallbackTemplates = [
  ...TEMPLATE_REGISTRY.map((template) => ({
    id: template.id,
    name: template.name,
    category: template.category,
    layout: template.layout,
    ats_level: template.atsLevel === "very-high" ? "optimized" : template.atsLevel,
    supports_photo: template.supportsPhoto,
    description: template.description,
    themes: template.themes,
    recommended_for: template.recommendedFor,
  })),
];

const filters = [
  "All",
  "ATS",
  "Professional",
  "Modern",
  "Executive",
];

const allowedTemplateIds = new Set(TEMPLATE_REGISTRY.map((template) => template.id));

export default function TemplateSwitcher({ onChange, resume, value }) {
  const [templates, setTemplates] = useState(fallbackTemplates);
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");
  const [selectedTemplateId, setSelectedTemplateId] = useState(value);
  const [previewTemplateId, setPreviewTemplateId] = useState(null);

  useEffect(() => {
    let ignore = false;

    async function loadTemplates() {
      try {
        const data = await listTemplates();
        const supportedTemplates = data
          .filter((template) => allowedTemplateIds.has(template.id))
          .map(withLocalMetadata);
        if (!ignore && supportedTemplates.length) {
          setTemplates(supportedTemplates);
        }
      } catch {
        if (!ignore) {
          setTemplates(fallbackTemplates);
        }
      }
    }

    loadTemplates();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    setSelectedTemplateId(value);
  }, [value]);

  useEffect(() => {
    if (!isOpen && !previewTemplateId) {
      return undefined;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setPreviewTemplateId(null);
        setIsOpen(false);
      }
      if (previewTemplateId && event.key === "ArrowLeft") {
        movePreview(-1);
      }
      if (previewTemplateId && event.key === "ArrowRight") {
        movePreview(1);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, previewTemplateId, templates]);

  const selectedTemplate =
    templates.find((template) => template.id === selectedTemplateId) ??
    templates.find((template) => template.id === value) ??
    templates[0];

  const visibleTemplates = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return templates.filter((template) => {
      const matchesSearch =
        !normalizedQuery ||
        [template.name, template.category, template.recommended_for?.join(" ")]
          .filter(Boolean)
          .some((text) => text.toLowerCase().includes(normalizedQuery));
      const matchesFilter =
        filter === "All" ||
        template.category === filter ||
        (filter === "ATS Optimized" && template.ats_level === "optimized") ||
        (filter === "With Photo" && template.supports_photo) ||
        (filter === "Without Photo" && !template.supports_photo) ||
        (filter === "Single Column" && template.layout === "single-column");
      return matchesSearch && matchesFilter;
    });
  }, [filter, query, templates]);

  function applyTemplate(templateId) {
    const template = templates.find((item) => item.id === templateId);
    if (template && shouldWarnForAts(template)) {
      const confirmed = window.confirm(
        "This layout is visually distinctive but may be less compatible with strict ATS systems.",
      );
      if (!confirmed) {
        return;
      }
    }
    onChange(templateId);
    setPreviewTemplateId(null);
    setIsOpen(false);
  }

  function openPreview(templateId) {
    setSelectedTemplateId(templateId);
    setPreviewTemplateId(templateId);
  }

  function movePreview(delta) {
    const currentIndex = templates.findIndex((template) => template.id === previewTemplateId);
    const nextIndex = (currentIndex + delta + templates.length) % templates.length;
    setPreviewTemplateId(templates[nextIndex].id);
    setSelectedTemplateId(templates[nextIndex].id);
  }

  return (
    <>
      <button
        className="template-gallery-trigger"
        onClick={() => setIsOpen(true)}
        type="button"
      >
        <span>Dossier template</span>
        <strong>{selectedTemplate?.name ?? "Choose"}</strong>
      </button>

      {isOpen && (
        <div
          aria-modal="true"
          className="template-modal-backdrop"
          onClick={() => setIsOpen(false)}
          role="dialog"
        >
          <section className="template-modal" onClick={(event) => event.stopPropagation()}>
            <header className="template-modal-header">
              <div className="template-modal-title">
                <p className="eyebrow">Template archive</p>
                <h2>Choose a dossier layout</h2>
              </div>
              <button className="secondary-button" onClick={() => setIsOpen(false)} type="button">
                Close
              </button>
            </header>

            <div className="template-gallery-controls">
              <label>
                Search templates
                <input
                  autoFocus
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search by name, category, or role"
                  value={query}
                />
              </label>
              <div className="template-filter-tabs" role="tablist" aria-label="Template filters">
                {filters.map((item) => (
                  <button
                    className={filter === item ? "active" : ""}
                    key={item}
                    onClick={() => setFilter(item)}
                    type="button"
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>

            <div className="template-gallery-layout">
              <div className="template-card-grid">
                {visibleTemplates.map((template) => (
                  <article
                    className={
                      selectedTemplateId === template.id
                        ? "template-card selected"
                        : "template-card"
                    }
                    key={template.id}
                  >
                    <TemplateThumb resume={resume} template={template} />
                    <div className="template-card-body">
                      <h3>{template.name}</h3>
                      <p>{template.category}</p>
                      <div className="template-chip-row">
                        <span>{atsLabel(template)}</span>
                        <span>{template.layout === "single-column" ? "Single column" : "Two column"}</span>
                        <span>{template.supports_photo ? "Photo" : "No photo"}</span>
                      </div>
                      <small>{template.description}</small>
                      <div className="template-card-actions">
                        <button
                          className="secondary-button"
                          onClick={() => openPreview(template.id)}
                          type="button"
                        >
                          Preview
                        </button>
                        <button
                          className="primary-link"
                          onClick={() => applyTemplate(template.id)}
                          type="button"
                        >
                          Use Template
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>

              <aside className="template-detail-panel">
                <TemplateThumb resume={resume} template={selectedTemplate} large />
                <h3>{selectedTemplate?.name}</h3>
                <p>{selectedTemplate?.category}</p>
                <dl>
                  <div>
                    <dt>ATS fit</dt>
                    <dd>{atsLabel(selectedTemplate)}</dd>
                  </div>
                  <div>
                    <dt>Layout</dt>
                    <dd>{selectedTemplate?.layout}</dd>
                  </div>
                  <div>
                    <dt>Photo</dt>
                    <dd>{selectedTemplate?.supports_photo ? "Supported" : "Not used"}</dd>
                  </div>
                  <div>
                    <dt>Best for</dt>
                    <dd>{selectedTemplate?.recommended_for?.join(", ")}</dd>
                  </div>
                </dl>
                {selectedTemplate && shouldWarnForAts(selectedTemplate) && (
                  <p className="ats-warning">
                    This layout is visually distinctive but may be less compatible with strict ATS systems.
                  </p>
                )}
                <button
                  className="download-button"
                  onClick={() => applyTemplate(selectedTemplate.id)}
                  type="button"
                >
                  Apply Template
                </button>
              </aside>
            </div>
          </section>
        </div>
      )}

      {previewTemplateId && (
        <div
          aria-modal="true"
          className="template-preview-backdrop"
          onClick={() => setPreviewTemplateId(null)}
          role="dialog"
        >
          <section className="template-preview-modal" onClick={(event) => event.stopPropagation()}>
            <header className="template-preview-header">
              <div className="template-modal-title">
                <p className="eyebrow">Dossier preview</p>
                <h2>{selectedTemplate?.name}</h2>
                <p>{selectedTemplate?.description}</p>
              </div>
              <button className="secondary-button" onClick={() => setPreviewTemplateId(null)} type="button">
                Close
              </button>
            </header>
            <div className="template-preview-body">
              <div className="template-preview-page">
                <TemplatePdfPreview
                  large
                  resume={resumePreviewData(resume, previewTemplateId)}
                  templateId={previewTemplateId}
                />
              </div>
              <aside className="template-preview-meta">
                <dl>
                  <div>
                    <dt>ATS compatibility</dt>
                    <dd>{atsLabel(selectedTemplate)}</dd>
                  </div>
                  <div>
                    <dt>Layout</dt>
                    <dd>{selectedTemplate?.layout}</dd>
                  </div>
                  <div>
                    <dt>Recommended for</dt>
                    <dd>{selectedTemplate?.recommended_for?.join(", ")}</dd>
                  </div>
                  <div>
                    <dt>Themes</dt>
                    <dd>{selectedTemplate?.themes?.join(", ")}</dd>
                  </div>
                </dl>
                <div className="template-preview-actions">
                  <button className="secondary-button" onClick={() => movePreview(-1)} type="button">
                    Previous
                  </button>
                  <button className="secondary-button" onClick={() => movePreview(1)} type="button">
                    Next
                  </button>
                  <button className="download-button" onClick={() => applyTemplate(previewTemplateId)} type="button">
                    Use Template
                  </button>
                </div>
              </aside>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

function TemplateThumb({ large = false, resume, template }) {
  const family = thumbnailFamily(template);
  return (
    <div className={large ? `template-thumb large ${family}` : `template-thumb ${family}`}>
      <div className="template-thumb-real">
        {template?.id ? (
          <TemplatePdfPreview
            resume={resumePreviewData(resume, template.id)}
            templateId={template.id}
          />
        ) : null}
      </div>
    </div>
  );
}

function TemplatePdfPreview({ large = false, resume, templateId }) {
  const [url, setUrl] = useState("");

  useEffect(() => {
    let cancelled = false;
    previewResumePdf({ ...resume, template_choice: templateId })
      .then((blob) => {
        if (cancelled) return;
        const nextUrl = URL.createObjectURL(blob);
        setUrl((current) => {
          if (current) URL.revokeObjectURL(current);
          return nextUrl;
        });
      })
      .catch(() => setUrl(""));
    return () => {
      cancelled = true;
    };
  }, [resume, templateId]);

  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url);
  }, [url]);

  return url ? (
    <iframe
      className={large ? "template-pdf-frame large" : "template-pdf-frame"}
      src={`${url}#toolbar=0&navpanes=0&view=FitH`}
      tabIndex="-1"
      title={`${templateId} PDF preview`}
    />
  ) : (
    <div className="template-pdf-loading"><span /></div>
  );
}

function resumePreviewData(resume, templateId) {
  const hasCandidate = Boolean(resume?.personal_info?.name?.trim());
  const source = hasCandidate ? resume : TEMPLATE_SAMPLE_RESUME;
  return { ...source, template_choice: templateId };
}

function thumbnailFamily(template) {
  if (!template) return "thumb-ats";
  if (template.supports_photo) return "thumb-photo-layout";
  if (template.category === "Executive") return "thumb-executive";
  if (template.category === "Professional") return "thumb-professional";
  if (template.category === "Technical" || template.category === "Data and Analytics") {
    return "thumb-technical";
  }
  if (template.category === "Creative") return "thumb-creative";
  if (template.layout === "two-column") return "thumb-modern";
  if (template.category === "Compact") return "thumb-compact";
  return "thumb-ats";
}

function withLocalMetadata(template) {
  const local = TEMPLATE_REGISTRY.find((item) => item.id === template.id);
  return {
    ...template,
    category: local?.category ?? template.category,
    layout: local?.layout ?? template.layout,
    description: local?.description ?? template.description,
    themes: local?.themes ?? template.themes,
    recommended_for: local?.recommendedFor ?? template.recommended_for,
  };
}

function atsLabel(template) {
  if (!template) return "ATS balanced";
  if (template.ats_level === "optimized") return "ATS optimized";
  if (template.ats_level === "high") return "High ATS fit";
  if (template.ats_level === "visual") return "Visual layout";
  return "ATS balanced";
}

function shouldWarnForAts(template) {
  return (
    template.ats_level === "visual" ||
    template.supports_photo ||
    template.layout === "two-column"
  );
}
