import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "../router.jsx";
import {
  analyzeResumeImport,
  analyzeSavedResume,
  archiveResume,
  createImportedResumeDraft,
  createResume,
  deleteResume,
  duplicateResume,
  exportResumePdf,
  fetchResume,
  listResumes,
  listTemplates,
  optimizeResumeWithAi,
  renameResume,
  restoreResume,
} from "../api/resumes.js";
import ResumeDocument from "../components/ResumeDocument.jsx";

const sortOptions = [
  { label: "Recently updated", value: "updated" },
  { label: "Created date", value: "created" },
  { label: "Title", value: "title" },
];

const statusFilters = [
  { label: "All", value: "all" },
  { label: "Draft", value: "draft" },
  { label: "Completed", value: "completed" },
  { label: "Archived", value: "archived" },
];

export default function DashboardPage() {
  const navigate = useNavigate();
  const [resumes, setResumes] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [resumeDetails, setResumeDetails] = useState({});
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("updated");
  const [statusFilter, setStatusFilter] = useState("all");
  const [templateFilter, setTemplateFilter] = useState("all");
  const [activeDownloadId, setActiveDownloadId] = useState(null);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [isExperienceLevelOpen, setIsExperienceLevelOpen] = useState(false);
  const [status, setStatus] = useState({
    type: "loading",
    message: "Loading resumes...",
  });

  async function loadDashboard() {
    setStatus({ type: "loading", message: "Loading resumes..." });
    try {
      const [resumeData, templateData] = await Promise.all([
        listResumes({ sort, status: statusFilter, template: templateFilter }),
        listTemplates(),
      ]);
      setResumes(resumeData);
      setTemplates(templateData);
      const detailPairs = await Promise.all(
        resumeData.map(async (resume) => {
          try {
            return [resume.id, await fetchResume(resume.id)];
          } catch {
            return [resume.id, resume];
          }
        }),
      );
      setResumeDetails(Object.fromEntries(detailPairs));
      setStatus({ type: "idle", message: "" });
    } catch (error) {
      setStatus({ type: "error", message: dashboardErrorMessage(error) });
    }
  }

  useEffect(() => {
    loadDashboard();
  }, [sort, statusFilter, templateFilter]);

  const filteredResumes = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return resumes.filter((resume) => {
      if (!normalizedQuery) {
        return true;
      }
      return [resume.title, resume.target_role, resume.template_choice]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(normalizedQuery));
    });
  }, [query, resumes]);

  const stats = useMemo(() => {
    const active = resumes.filter((resume) => resume.status !== "archived");
    return {
      total: resumes.length,
      drafts: active.filter((resume) => resume.status !== "completed").length,
      completed: active.filter((resume) => resume.status === "completed").length,
      templates: templates.length,
      downloads: resumes.reduce((sum, resume) => sum + Number(resume.download_count || 0), 0),
      averageAts: average(
        resumes.map((resume) => resume.ats_score),
      ),
    };
  }, [resumes, templates]);

  const analytics = useMemo(
    () => buildDashboardAnalytics(resumes, resumeDetails, templates),
    [resumes, resumeDetails, templates],
  );

  function handleCreate() {
    setIsExperienceLevelOpen(true);
  }

  async function createResumeForExperienceLevel(experienceLevel) {
    setIsExperienceLevelOpen(false);
    setStatus({ type: "loading", message: "Creating resume..." });
    try {
      const created = await createResume("Untitled Resume", "steady-form", experienceLevel);
      navigate(`/resume/${created.id}`);
    } catch (error) {
      setStatus({ type: "error", message: dashboardErrorMessage(error) });
    }
  }

  async function handleDuplicate(resume) {
    setStatus({ type: "loading", message: "Creating targeted version..." });
    try {
      const duplicate = await duplicateResume(resume.id, `${resume.title} Version`);
      navigate(`/resume/${duplicate.id}`);
    } catch (error) {
      setStatus({ type: "error", message: dashboardErrorMessage(error) });
    }
  }

  async function handleRename(resume) {
    const title = window.prompt("Resume name", resume.title);
    if (!title || title.trim() === resume.title) {
      return;
    }
    setStatus({ type: "loading", message: "Renaming resume..." });
    try {
      await renameResume(resume.id, title.trim());
      await loadDashboard();
    } catch (error) {
      setStatus({ type: "error", message: dashboardErrorMessage(error) });
    }
  }

  async function handleArchiveToggle(resume) {
    setStatus({
      type: "loading",
      message: resume.status === "archived" ? "Restoring resume..." : "Archiving resume...",
    });
    try {
      if (resume.status === "archived") {
        await restoreResume(resume.id);
      } else {
        await archiveResume(resume.id);
      }
      await loadDashboard();
    } catch (error) {
      setStatus({ type: "error", message: dashboardErrorMessage(error) });
    }
  }

  async function handleDownload(resume) {
    setActiveDownloadId(resume.id);
    setStatus({ type: "loading", message: "Generating PDF..." });
    try {
      const { blob, filename } = await exportResumePdf(
        resume.id,
        resume.template_choice,
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
      await loadDashboard();
      setStatus({ type: "success", message: "PDF download started." });
    } catch (error) {
      setStatus({ type: "error", message: dashboardErrorMessage(error) });
    } finally {
      setActiveDownloadId(null);
    }
  }

  async function handleDelete(resume) {
    const confirmed = window.confirm(
      `Delete "${resume.title}"? This cannot be undone.`,
    );
    if (!confirmed) {
      return;
    }

    setStatus({ type: "loading", message: "Deleting resume..." });
    try {
      await deleteResume(resume.id);
      await loadDashboard();
    } catch (error) {
      setStatus({ type: "error", message: dashboardErrorMessage(error) });
    }
  }

  return (
    <section className="dashboard-page resume-dashboard">
      <div className="dashboard-header">
        <div>
          <p className="eyebrow">Career command center</p>
          <h1>Build, tailor, measure, apply.</h1>
          <p>Manage targeted resumes, track ATS readiness, and export recruiter-ready PDFs from one workspace.</p>
        </div>
        <div className="dashboard-header-actions">
          <button
            className="secondary-button upload-resume-button"
            disabled={status.type === "loading"}
            onClick={() => setIsImportOpen((current) => !current)}
            type="button"
          >
            Import resume
          </button>
          <button
            className="primary-link"
            disabled={status.type === "loading"}
            onClick={handleCreate}
            type="button"
          >
            Create resume
          </button>
        </div>
      </div>

      {isExperienceLevelOpen && (
        <div className="modal-backdrop experience-level-backdrop" onMouseDown={() => setIsExperienceLevelOpen(false)}>
          <section
            aria-labelledby="experience-level-dialog-title"
            aria-modal="true"
            className="modal-box experience-level-dialog"
            onMouseDown={(event) => event.stopPropagation()}
            role="dialog"
          >
            <p className="eyebrow">Create resume</p>
            <h2 id="experience-level-dialog-title">Choose your experience level</h2>
            <p>This sets up the recommended resume sections and AI-writing guidance. You can change any section later.</p>
            <div className="experience-level-options">
              <button className="experience-level-option" onClick={() => createResumeForExperienceLevel("fresher")} type="button">
                <strong>Fresher</strong>
                <span>Student, recent graduate, or no full-time work experience yet.</span>
              </button>
              <button className="experience-level-option" onClick={() => createResumeForExperienceLevel("experienced")} type="button">
                <strong>Experienced professional</strong>
                <span>Have internships, employment, freelance, or other work experience.</span>
              </button>
            </div>
            <div className="modal-actions">
              <button className="secondary-button" onClick={() => setIsExperienceLevelOpen(false)} type="button">Cancel</button>
            </div>
          </section>
        </div>
      )}

      {isImportOpen && (
        <ResumeImportPanel
          onCancel={() => setIsImportOpen(false)}
          onImported={(resume, state) => navigate(`/resume/${resume.id}`, { state })}
        />
      )}

      <div className="dashboard-stats" aria-label="Resume summary">
        <StatCard icon="📄" label="Total resumes" value={stats.total} />
        <StatCard icon="📝" label="Active drafts" value={stats.drafts} />
        <StatCard icon="✅" label="Completed" value={stats.completed} />
        <StatCard icon="🎨" label="Templates" value={stats.templates} />
        <StatCard icon="◎" label="Average ATS" value={stats.averageAts === null ? "—" : `${stats.averageAts}%`} />
        <StatCard icon="⬇️" label="PDF exports" value={stats.downloads} />
      </div>

      <ResumeAnalyticsDashboard analytics={analytics} />

      <section className="dashboard-workflow" aria-label="Recommended resume workflow">
        <div className="dashboard-workflow__intro">
          <p className="eyebrow">Recommended workflow</p>
          <h2>Move from source resume to targeted application.</h2>
          <p>Each version stays editable, autosaved, measurable, and connected to the same four-template system.</p>
        </div>
        <ol>
          <li><span>01</span><strong>Import or create</strong><small>Start clean or reuse verified content.</small></li>
          <li><span>02</span><strong>Write with AI</strong><small>Review every summary and achievement.</small></li>
          <li><span>03</span><strong>Check ATS fit</strong><small>Compare structure and target keywords.</small></li>
          <li><span>04</span><strong>Preview and export</strong><small>Verify the exact text-based PDF.</small></li>
        </ol>
      </section>

      <section className="dashboard-control-panel" aria-label="Resume dossier controls">
        <div className="dashboard-control-panel__heading">
          <p className="eyebrow">Dossier archive</p>
          <h2>Find the right resume record.</h2>
        </div>
        <div className="dashboard-toolbar">
          <label>
            Search resumes
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by title, role, or template"
              value={query}
            />
          </label>
          <label>
            Status
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              {statusFilters.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Template
            <select value={templateFilter} onChange={(event) => setTemplateFilter(event.target.value)}>
              <option value="all">All templates</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Sort
            <select value={sort} onChange={(event) => setSort(event.target.value)}>
              {sortOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button className="secondary-button" onClick={loadDashboard} type="button">
            Refresh
          </button>
        </div>
      </section>

      {status.message && (
        <div className={`status-message ${status.type}`} role="status">
          <span>{status.message}</span>
          {status.type === "error" && (
            <button className="secondary-button" onClick={loadDashboard} type="button">
              Retry
            </button>
          )}
        </div>
      )}

      {status.type !== "loading" && status.type !== "error" && filteredResumes.length === 0 && (
        <div className="empty-state">
          <h2>No matching resumes</h2>
          <p>Create a resume or adjust your filters to see active drafts.</p>
          <button className="primary-link" onClick={handleCreate} type="button">
            Create resume
          </button>
        </div>
      )}

      <section className="recent-resumes" aria-label="Recently edited resumes">
        <div className="recent-resumes__heading">
          <p className="eyebrow">Recently edited</p>
          <h2>{filteredResumes.length} resume dossier{filteredResumes.length === 1 ? "" : "s"}</h2>
        </div>
        <div className="resume-card-grid">
          {filteredResumes.map((resume) => {
            const completion = clampPercentage(resume.completion_percentage);
            const resumeTitle = resume.title || "Untitled Resume";
            return (
            <article className="resume-card" key={resume.id}>
              <div className="resume-card__accent" aria-hidden="true" />
              <div className="resume-card__layout">
                <ResumeCardThumbnail resume={resumeDetails[resume.id] || resume} />
                <div className="resume-card__content">
                  <div className="resume-card__identity">
                    <span className={`status-pill ${resume.status || "draft"}`}>
                      {resume.status || "draft"}
                    </span>
                    <h3 className="resume-card__title" title={resumeTitle}>{resumeTitle}</h3>
                    <p className="resume-card__role" title={resume.target_role || "No target role set"}>
                      {resume.target_role || "No target role set"}
                    </p>
                  </div>
                  <dl className="resume-card__metadata">
                    <div className="resume-card__metadata-item">
                      <dt className="resume-card__metadata-label">Template</dt>
                      <dd className="resume-card__metadata-value">{templateName(templates, resume.template_choice)}</dd>
                    </div>
                    <div className="resume-card__metadata-item">
                      <dt className="resume-card__metadata-label">Updated</dt>
                      <dd className="resume-card__metadata-value">{formatDateTime(resume.updated_at)}</dd>
                    </div>
                    <div className="resume-card__metadata-item">
                      <dt className="resume-card__metadata-label">Complete</dt>
                      <dd className="resume-card__metadata-value">{completion}%</dd>
                    </div>
                    <div className="resume-card__metadata-item">
                      <dt className="resume-card__metadata-label">Downloaded</dt>
                      <dd className="resume-card__metadata-value">{resume.last_downloaded_at ? formatDateTime(resume.last_downloaded_at) : "Not yet"}</dd>
                    </div>
                  </dl>
                  <div className="completion-meter" aria-label={`${completion}% complete`}>
                    <span className="resume-card__progress-fill" style={{ width: `${completion}%` }} />
                  </div>
                </div>
              </div>
              <div className="resume-card__actions">
                <Link className="resume-card__action secondary-button" aria-label={`Open or edit ${resumeTitle}`} to={`/resume/${resume.id}`}>
                  Open/Edit
                </Link>
                <Link className="resume-card__action secondary-button" aria-label={`Preview ${resumeTitle}`} to={`/resume/${resume.id}`}>
                  Preview
                </Link>
                <button
                  className="resume-card__action download-button"
                  disabled={activeDownloadId === resume.id || status.type === "loading"}
                  onClick={() => handleDownload(resume)}
                  type="button"
                >
                  {activeDownloadId === resume.id ? "Downloading..." : "Download PDF"}
                </button>
                <button className="resume-card__action secondary-button" onClick={() => handleDuplicate(resume)} type="button">Duplicate</button>
                <button className="resume-card__action secondary-button" onClick={() => handleRename(resume)} type="button">Rename</button>
                <button className="resume-card__action secondary-button" onClick={() => handleArchiveToggle(resume)} type="button">
                  {resume.status === "archived" ? "Restore" : "Archive"}
                </button>
                <button className="resume-card__action resume-card__action--delete danger-button" onClick={() => handleDelete(resume)} type="button">Delete</button>
              </div>
            </article>
          );
          })}
        </div>
      </section>
    </section>
  );
}

function ResumeAnalyticsDashboard({ analytics }) {
  return (
    <section className="resume-analytics-dashboard" aria-label="Resume analytics dashboard">
      <div className="resume-analytics-dashboard__header">
        <div>
          <p className="eyebrow">Analytics dashboard</p>
          <h2>Resume performance snapshot</h2>
        </div>
        <p>{analytics.summary}</p>
      </div>

      <div className="analytics-kpi-grid">
        {analytics.kpis.map((item) => (
          <article className="analytics-kpi" key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <small>{item.detail}</small>
          </article>
        ))}
      </div>

      <section className="analytics-readiness" aria-label="Resume readiness distribution">
        <div className="analytics-readiness__score">
          <span className="analytics-readiness__label">Portfolio readiness</span>
          <strong>{analytics.readiness.score}%</strong>
          <p>{analytics.readiness.detail}</p>
        </div>
        <div className="analytics-readiness__content">
          <div className="analytics-readiness__heading">
            <div>
              <h3>Readiness distribution</h3>
              <p>Completion and ATS results combined into one practical view.</p>
            </div>
            <span>{analytics.readiness.scoredCount} scored</span>
          </div>
          <div className="analytics-readiness__bars">
            {analytics.readiness.bands.map((band) => (
              <div className="analytics-readiness__bar" key={band.label}>
                <div>
                  <span>{band.label}</span>
                  <strong>{band.value}</strong>
                </div>
                <div className="analytics-bar-track" aria-hidden="true">
                  <span style={{ width: `${band.percent}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="analytics-dashboard-grid">
        <AnalyticsBarList title="Target role focus" items={analytics.roles} emptyText="Add target roles to compare resume focus." />
        <AnalyticsBarList title="Template usage" items={analytics.templates} emptyText="Create resumes to see template distribution." />
        <AnalyticsBarList title="Token use by resume" items={analytics.tokens} emptyText="Add resume content to estimate token usage." />
        <AnalyticsBarList title="Content gaps" items={analytics.gaps} emptyText="Core resume sections look complete." />
      </div>

      <div className="analytics-insight-row">
        <article>
          <h3>Top ATS candidates</h3>
          {analytics.topResumes.length ? (
            <ol>
              {analytics.topResumes.map((resume) => (
                <li key={resume.id}>
                  <span>{resume.title}</span>
                  <strong>{resume.score}%</strong>
                </li>
              ))}
            </ol>
          ) : (
            <p>No ATS scores yet. Run an ATS check to rank resumes.</p>
          )}
        </article>
        <article>
          <h3>Next best actions</h3>
          <ul>
            {analytics.actions.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ul>
        </article>
      </div>
    </section>
  );
}

function AnalyticsBarList({ emptyText, items, title }) {
  return (
    <article className="analytics-bar-card">
      <h3>{title}</h3>
      {items.length ? (
        <div className="analytics-bar-list">
          {items.map((item) => (
            <div className="analytics-bar-item" key={item.label}>
              <div>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
              <div className="analytics-bar-track" aria-hidden="true">
                <span style={{ width: `${item.percent}%` }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p>{emptyText}</p>
      )}
    </article>
  );
}

function StatCard({ icon, label, value }) {
  return (
    <div className="stat-card">
      <span className="stat-card__icon" aria-hidden="true">{icon}</span>
      <div className="stat-card__content">
        <span className="stat-card__value">{value}</span>
        <p className="stat-card__label">{label}</p>
      </div>
    </div>
  );
}

function ResumeImportPanel({ onCancel, onImported }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [jobDescription, setJobDescription] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [result, setResult] = useState(null);
  const [parsedResume, setParsedResume] = useState(null);
  const [message, setMessage] = useState({ type: "info", text: "" });
  const [isDragging, setIsDragging] = useState(false);
  const [phase, setPhase] = useState("idle");
  const [isGeneratingAiResume, setIsGeneratingAiResume] = useState(false);
  const requestInFlightRef = useRef(false);

  const isBusy = phase === "analyzing" || phase === "importing" || isGeneratingAiResume;
  const resolvedTargetRole = targetRole.trim() || parsedResume?.targetRole || parsedResume?.title || "";

  function resetSelection() {
    setSelectedFile(null);
    setResult(null);
    setParsedResume(null);
    setTargetRole("");
    setPhase("idle");
    setMessage({ type: "info", text: "" });
  }

  function validateFile(file) {
    if (!file) return "Choose a .txt resume file.";
    const supportedExtensions = [".pdf", ".doc", ".docx", ".txt"];
    const supportedTypes = [
      "application/pdf",
      "application/msword",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "text/plain",
      "text/markdown",
      "",
    ];
    if (!supportedExtensions.some((extension) => file.name.toLowerCase().endsWith(extension))) {
      return "Upload your resume in PDF, Word (.doc or .docx), or TXT format. Maximum file size: 5 MB.";
    }
    if (file.type && !supportedTypes.includes(file.type)) {
      return "File type does not match a supported PDF, Word, or TXT resume.";
    }
    if (file.size > 5 * 1024 * 1024) return "Resume file must be 5 MB or smaller.";
    if (file.size === 0) return "The uploaded resume is empty.";
    return "";
  }

  function selectFile(file) {
    const error = validateFile(file);
    if (error) {
      resetSelection();
      setMessage({ type: "error", text: error });
      return;
    }
    setSelectedFile(file);
    setResult(null);
    setParsedResume(null);
    setPhase("selected");
    setMessage({ type: "success", text: `${file.name} selected.` });
  }

  async function analyzeFile() {
    if (!selectedFile || isBusy || requestInFlightRef.current) return;
    requestInFlightRef.current = true;
    setPhase("analyzing");
    setMessage({ type: "info", text: "Analyzing resume..." });
    try {
      const analysis = await analyzeResumeImport({ file: selectedFile, jobDescription, targetRole });
      setResult(analysis);
      setParsedResume(analysis.parsedResume);
      setPhase("review");
      setMessage({ type: "success", text: "Analysis complete. Review extracted fields before import." });
    } catch (error) {
      setPhase("selected");
      setMessage({ type: "error", text: dashboardErrorMessage(error) });
    } finally {
      requestInFlightRef.current = false;
    }
  }

  async function importDraft() {
    if (!parsedResume || isBusy || requestInFlightRef.current) return;
    const missingContactFields = [];
    if (!parsedResume.personalInfo?.fullName?.trim()) missingContactFields.push("full name");
    if (!parsedResume.personalInfo?.email?.trim()) missingContactFields.push("email");
    if (missingContactFields.length) {
      setMessage({
        type: "error",
        text: `Before importing, enter your ${missingContactFields.join(" and ")} in the Parsed resume preview.`,
      });
      return;
    }
    requestInFlightRef.current = true;
    setPhase("importing");
    setMessage({ type: "info", text: "Creating editable resume draft..." });
    try {
      const resumeForImport = {
        ...parsedResume,
        targetRole: resolvedTargetRole || parsedResume.targetRole,
      };
      const created = await createImportedResumeDraft({
        originalFileName: result?.originalFileName || selectedFile?.name || "resume.txt",
        parsedResume: resumeForImport,
        atsAnalysis: result?.atsAnalysis,
      });
      setMessage({ type: "success", text: "Imported resume draft created." });
      onImported(created);
    } catch (error) {
      setPhase("review");
      setMessage({ type: "error", text: dashboardErrorMessage(error) });
    } finally {
      requestInFlightRef.current = false;
    }
  }

  async function generateAiResume() {
    if (!parsedResume || isBusy || requestInFlightRef.current) return;
    if (!resolvedTargetRole) {
      setMessage({ type: "error", text: "Add a target role or update the extracted target role before generating AI content." });
      return;
    }
    const missingContactFields = [];
    if (!parsedResume.personalInfo?.fullName?.trim()) missingContactFields.push("full name");
    if (!parsedResume.personalInfo?.email?.trim()) missingContactFields.push("email");
    if (missingContactFields.length) {
      setMessage({
        type: "error",
        text: `Before generating, enter your ${missingContactFields.join(" and ")} in the Parsed resume preview. We will not save a resume with placeholder contact details.`,
      });
      return;
    }
    requestInFlightRef.current = true;
    setIsGeneratingAiResume(true);
      setMessage({ type: "info", text: `Generating your complete AI resume for: ${resolvedTargetRole}...` });
    let currentStep = "AI generation";
    try {
      const data = await optimizeResumeWithAi({
        resume: parsedResume,
        targetRole: resolvedTargetRole,
        jobDescription,
      });
      const generatedResume = {
        ...parsedResume,
        targetRole: resolvedTargetRole,
        summary: data.resume.summary ?? parsedResume.summary,
        skills: data.resume.skills ?? parsedResume.skills,
        experience: (parsedResume.experience ?? []).map((item, index) => ({
          ...item,
          ai_generated_bullets: data.resume.experience?.[index]?.ai_generated_bullets ?? item.ai_generated_bullets,
        })),
        projects: (parsedResume.projects ?? []).map((item, index) => ({
          ...item,
          ai_generated_bullets: data.resume.projects?.[index]?.ai_generated_bullets ?? item.ai_generated_bullets,
        })),
        education: data.resume.education ?? parsedResume.education,
        certifications: data.resume.certifications ?? parsedResume.certifications,
        achievements: data.resume.achievements ?? parsedResume.achievements,
        declaration: data.resume.declaration ?? parsedResume.declaration,
      };
      const skipped = Array.isArray(data.skipped) ? data.skipped : [];
      setParsedResume(generatedResume);
      setMessage({ type: "info", text: "Saving your AI-generated resume and preparing the PDF..." });
      currentStep = "saving the AI-generated resume";
      const created = await createImportedResumeDraft({
        originalFileName: result?.originalFileName || selectedFile?.name || "resume.txt",
        parsedResume: generatedResume,
        atsAnalysis: result?.atsAnalysis,
      });
      // Persist an ATS result for the generated content rather than retaining
      // the score calculated for the pre-generation upload.
      let refreshedAnalysis = null;
      let atsRefreshWarning = "";
      try {
        refreshedAnalysis = await analyzeSavedResume(
          created.id, jobDescription, resolvedTargetRole,
        );
      } catch (error) {
        // The resume has already been saved successfully. Keep download
        // available and let the user rerun ATS analysis from the builder.
        atsRefreshWarning = " Resume created, but ATS refresh was unavailable; rerun ATS analysis in the editor.";
      }
      currentStep = "downloading the AI-generated PDF";
      const { blob, filename } = await exportResumePdf(created.id, created.template_choice);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 4000);
      setMessage({ type: "success", text: `Complete AI resume created, ATS-scored, and PDF download started.${atsRefreshWarning}` });
      onImported(created, {
        atsAnalysis: refreshedAnalysis,
          aiGeneration: {
            skipped,
            generated: data.generated ?? {},
            roleAlignment: data.role_alignment ?? null,
          },
      });
    } catch (error) {
      setMessage({
        type: "error",
        text: `${currentStep} failed: ${dashboardErrorMessage(error, { preferBackendMessage: true })}`,
      });
    } finally {
      setIsGeneratingAiResume(false);
      requestInFlightRef.current = false;
    }
  }

  function updatePersonal(field, value) {
    setParsedResume((current) => ({
      ...current,
      personalInfo: { ...(current?.personalInfo ?? {}), [field]: value },
    }));
  }

  function updateField(field, value) {
    setParsedResume((current) => ({ ...current, [field]: value }));
  }

  function updateArrayItem(section, index, field, value) {
    setParsedResume((current) => ({
      ...current,
      [section]: current[section].map((item, itemIndex) =>
        itemIndex === index ? { ...item, [field]: value } : item,
      ),
    }));
  }

  function removeArrayItem(section, index) {
    setParsedResume((current) => ({
      ...current,
      [section]: current[section].filter((_item, itemIndex) => itemIndex !== index),
    }));
  }

  return (
    <section className="resume-import-panel">
      <div className="import-panel-heading">
        <div>
          <p className="eyebrow">Import resume</p>
          <h2>Analyze an existing resume</h2>
          <p>
            Upload your resume in PDF, Word (.doc or .docx), or TXT format. Maximum file size: 5 MB.
            We'll analyze its ATS compatibility and let you review the extracted information before importing it.
          </p>
          <p className="import-note">Scanned or image-only PDFs may require OCR and can produce less accurate results.</p>
        </div>
        <button className="secondary-button" disabled={isBusy} onClick={onCancel} type="button">
          Close
        </button>
      </div>

      <div
        className={isDragging ? "import-dropzone dragging" : "import-dropzone"}
        onDragEnter={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragging(false);
          selectFile(event.dataTransfer.files?.[0]);
        }}
      >
        <div className="upload-icon" aria-hidden="true">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        </div>
        <strong>Drop your resume here</strong>
        <span>Supported formats: PDF, DOC, DOCX, TXT. Maximum size: 5 MB.</span>
        <div className="format-badges" aria-label="Supported formats">
          <span>PDF</span>
          <span>DOCX</span>
          <span>DOC</span>
          <span>TXT</span>
        </div>
        <label className="primary-link import-file-button">
          Choose Resume
          <input
            accept=".pdf,.doc,.docx,.txt,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            disabled={isBusy}
            onChange={(event) => {
              selectFile(event.target.files?.[0]);
              event.target.value = "";
            }}
            type="file"
            style={{ display: "none" }}
          />
        </label>
      </div>

      {selectedFile && (
        <div className="selected-file-row">
          <div>
            <strong>{selectedFile.name}</strong>
            <span>{fileTypeLabel(selectedFile)} - {formatFileSize(selectedFile.size)}</span>
          </div>
          <button className="secondary-button" disabled={isBusy} onClick={resetSelection} type="button">
            Replace file
          </button>
        </div>
      )}

      <label>
        Target role
        <input
          disabled={isBusy}
          onChange={(event) => setTargetRole(event.target.value)}
          placeholder="Digital Marketing Executive"
          value={targetRole}
        />
      </label>

      <label>
        Optional job description
        <textarea
          disabled={isBusy}
          onChange={(event) => setJobDescription(event.target.value)}
          placeholder="Paste a job description to calculate a separate job match score."
          rows="4"
          value={jobDescription}
        />
      </label>

      <div className="import-actions">
        <button className="primary-link" disabled={!selectedFile || isBusy} onClick={analyzeFile} type="button">
          {phase === "analyzing" ? "Analyzing..." : "Analyze Resume"}
        </button>
        <button className="secondary-button" disabled={isBusy} onClick={resetSelection} type="button">
          Cancel
        </button>
      </div>

      {isBusy && <div className="import-progress"><span /></div>}
      {message.text && <p className={`status-message ${message.type}`}>{message.text}</p>}

      {result && parsedResume && (
        <div className="import-results-grid">
          <ImportScore analysis={result.atsAnalysis} />
          {result.extractionWarnings?.length > 0 && (
            <section className="import-extraction-warnings">
              <h3>Extraction warnings</h3>
              <ul>{result.extractionWarnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            </section>
          )}
          <ImportRecommendations analysis={result.atsAnalysis} unmapped={result.unmappedContent} />
          <ParsedResumeEditor
            onRemove={removeArrayItem}
            onUpdateArrayItem={updateArrayItem}
            onUpdateField={updateField}
            onUpdatePersonal={updatePersonal}
            parsedResume={parsedResume}
            unmapped={result.unmappedContent}
          />
          <div className="import-confirm-row">
            <p className="import-note">AI target role: {resolvedTargetRole || "Not specified"}</p>
            <button className="secondary-button" disabled={isBusy} onClick={analyzeFile} type="button">
              Analyze Again
            </button>
            <button className="secondary-button" disabled={isBusy} onClick={generateAiResume} type="button">
              {isGeneratingAiResume ? "Generating Complete Resume..." : "Generate Complete AI Resume & Download"}
            </button>
            <button className="download-button" disabled={isBusy} onClick={importDraft} type="button">
              {phase === "importing" ? "Importing..." : "Import into Resume Builder"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function ImportScore({ analysis }) {
  const score =
    typeof analysis.score === "object"
      ? analysis.score.normalized_score
      : analysis.score;
  const rating =
    typeof analysis.score === "object"
      ? analysis.score.classification
      : analysis.rating;
  return (
    <section className="import-score-card">
      <div className="import-score-header">
        <div className="ats-score-ring import-score-ring" style={{ "--score": `${score}%` }}>
          <strong>{score}</strong>
          <span>{rating}</span>
        </div>
        <div className="import-score-meta">
          <p className="eyebrow">{analysis.analysis_type === "job_match" ? "ATS Compatibility Estimate" : "Resume Quality Score"}</p>
          <h3>{rating}</h3>
          <p className="import-score-summary">{analysis.clarification || analysis.summary}</p>
          <dl className="import-check-counts">
            <div><dt>Passed</dt><dd className="count-passed">{analysis.passedChecks}</dd></div>
            <div><dt>Warnings</dt><dd className="count-warning">{analysis.warningCount}</dd></div>
            <div><dt>Critical</dt><dd className="count-critical">{analysis.criticalIssueCount}</dd></div>
          </dl>
        </div>
      </div>
      <div className="score-breakdown">
        <div className="score-breakdown-intro">
          <h4>Detailed Category Analysis</h4>
          <p>
            Each category shows the points earned out of its maximum, what evidence was checked, and the reason for the result.
            <strong> Passed</strong> means at least 80% of that category's points were earned; <strong>Warning</strong> means 45–79%;
            <strong> Critical</strong> means below 45%. <strong>Not Applicable</strong> categories are excluded from the overall estimate because the job description does not provide enough relevant requirements to score them fairly.
          </p>
        </div>
        {analysis.categories.map((item) => {
          const status = item.applicable === false ? "Not Applicable" : item.status;
          const statusClass = status.toLowerCase().replace(/\s+/g, "-");
          return (
          <article key={item.category} className={`breakdown-item status-${statusClass}`}>
            <div className="breakdown-item-head">
              <strong>{item.category}</strong>
              <span className={`status-badge badge-${statusClass}`}>{status}</span>
            </div>
            <p className="breakdown-explanation">
              <strong>{item.pointsEarned}/{item.maxPoints} pts</strong> — {item.explanation}
            </p>
            {item.recommendedAction && <small className="breakdown-action">💡 {item.recommendedAction}</small>}
          </article>
          );
        })}
      </div>
    </section>
  );
}

function ImportRecommendations({ analysis, unmapped }) {
  const grouped = ["Critical", "Important", "Optional", "High", "Medium"].map((priority) => ({
    priority,
    items: analysis.recommendations.filter((item) => item.priority === priority),
  }));
  return (
    <section className="import-recommendations">
      <h3>Strengths</h3>
      <ul>{analysis.strengths.map((item) => <li key={item}>{item}</li>)}</ul>
      <h3>Critical issues</h3>
      {analysis.criticalIssues.length ? (
        <ul>{analysis.criticalIssues.map((item) => <li key={item.problem}>{item.problem}: {item.whyItMatters}</li>)}</ul>
      ) : <p>No critical issues detected.</p>}
      <h3>Improvements</h3>
      {grouped.map((group) => group.items.length > 0 && (
        <div key={group.priority}>
          <strong>{group.priority} priority</strong>
          {group.items.map((item) => (
            <article className="import-recommendation" key={`${item.priority}-${item.problem}`}>
              <h4>{item.problem}</h4>
              <p>{item.why_it_matters || item.whyItMatters}</p>
              <small>{item.exact_fix || item.suggestedImprovement} Section: {item.section}</small>
            </article>
          ))}
        </div>
      ))}
      {unmapped.length > 0 && <p className="status-message info">{unmapped.length} unmapped line(s) need review.</p>}
    </section>
  );
}

function ParsedResumeEditor({ onRemove, onUpdateArrayItem, onUpdateField, onUpdatePersonal, parsedResume, unmapped }) {
  const info = parsedResume.personalInfo ?? {};
  return (
    <section className="parsed-resume-editor">
      <h3>Parsed resume preview</h3>
      <div className="form-grid">
        {["fullName", "email", "phone", "location", "linkedin", "github", "portfolio"].map((field) => (
          <label key={field}>
            {labelize(field)}
            <input value={info[field] ?? ""} onChange={(event) => onUpdatePersonal(field, event.target.value)} />
          </label>
        ))}
      </div>
      <label>
        Target role
        <input value={parsedResume.targetRole ?? ""} onChange={(event) => onUpdateField("targetRole", event.target.value)} />
      </label>
      <label>
        Professional summary
        <textarea rows="4" value={parsedResume.summary ?? ""} onChange={(event) => onUpdateField("summary", event.target.value)} />
      </label>
      <EditableList title="Skills" section="skills" items={parsedResume.skills ?? []} fields={["skill_name"]} onRemove={onRemove} onUpdate={onUpdateArrayItem} />
      <EditableList title="Education" section="education" items={parsedResume.education ?? []} fields={["school", "degree", "field", "end_date", "cgpa"]} onRemove={onRemove} onUpdate={onUpdateArrayItem} />
      <EditableList title="Experience" section="experience" items={parsedResume.experience ?? []} fields={["role", "company", "start_date", "end_date", "raw_input"]} onRemove={onRemove} onUpdate={onUpdateArrayItem} />
      <EditableList title="Projects" section="projects" items={parsedResume.projects ?? []} fields={["title", "description"]} onRemove={onRemove} onUpdate={onUpdateArrayItem} />
      <EditableList title="Certifications" section="certifications" items={parsedResume.certifications ?? []} fields={["name", "issuer", "date"]} onRemove={onRemove} onUpdate={onUpdateArrayItem} />
      <EditableList title="Languages" section="languages" items={parsedResume.languages ?? []} fields={["language_name", "proficiency"]} onRemove={onRemove} onUpdate={onUpdateArrayItem} />
      <section className="unmapped-content">
        <h4>Unmapped content</h4>
        {unmapped.length ? <ul>{unmapped.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p>No unmapped content.</p>}
      </section>
    </section>
  );
}

function EditableList({ fields, items, onRemove, onUpdate, section, title }) {
  if (section === "skills") {
    return (
      <section className="editable-import-section">
        <h4>{title}</h4>
        {items.length === 0 ? (
          <p>No {title.toLowerCase()} detected.</p>
        ) : (
          <article className="editable-skill-card">
            {items.map((item, index) => (
              <div className="editable-skill-row" key={`${section}-${index}`}>
                <label>
                  {labelize(fields[0])}
                  <input
                    value={item[fields[0]] ?? ""}
                    onChange={(event) =>
                      onUpdate(section, index, fields[0], event.target.value)
                    }
                  />
                </label>
                <button
                  className="secondary-button"
                  onClick={() => onRemove(section, index)}
                  type="button"
                >
                  Remove
                </button>
              </div>
            ))}
          </article>
        )}
      </section>
    );
  }

  return (
    <section className="editable-import-section">
      <h4>{title}</h4>
      {items.length === 0 ? <p>No {title.toLowerCase()} detected.</p> : items.map((item, index) => (
        <article key={`${section}-${index}`}>
          {fields.map((field) => (
            <label key={field}>
              {labelize(field)}
              {field === "raw_input" || field === "description" ? (
                <textarea rows="3" value={item[field] ?? ""} onChange={(event) => onUpdate(section, index, field, event.target.value)} />
              ) : (
                <input value={item[field] ?? ""} onChange={(event) => onUpdate(section, index, field, event.target.value)} />
              )}
            </label>
          ))}
          <button className="secondary-button" onClick={() => onRemove(section, index)} type="button">Remove</button>
        </article>
      ))}
    </section>
  );
}

function labelize(value) {
  return value.replace(/_/g, " ").replace(/([A-Z])/g, " $1").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatFileSize(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(2)} MB`;
}

function fileTypeLabel(file) {
  const extension = file.name.split(".").pop()?.toUpperCase() || "File";
  return file.type ? `${extension} (${file.type})` : extension;
}

function ResumeCardThumbnail({ resume }) {
  return (
    <div className="resume-card__thumbnail resume-thumbnail real-thumbnail" aria-label={`${resume.title} preview`}>
      <div className="resume-thumbnail-scale">
        <ResumeDocument resumeData={resume} templateId={resume.template_choice} />
      </div>
    </div>
  );
}

function clampPercentage(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return 0;
  }
  return Math.min(100, Math.max(0, Math.round(number)));
}

function dashboardErrorMessage(error, { preferBackendMessage = false } = {}) {
  if (preferBackendMessage && error.message) {
    return error.message;
  }
  if (error.type === "unavailable" || error.type === "timeout") {
    return `${error.message}. Confirm the Flask backend is running on port 5000.`;
  }
  if (error.type === "auth") {
    return "You are not authorized to load these resumes.";
  }
  if (error.type === "validation") {
    return error.message || "Some resume data needs attention.";
  }
  if (error.type === "database") {
    return "The database is unavailable. Check backend database settings and retry.";
  }
  if (error.type === "server") {
    return "The backend hit an unexpected error. Retry after checking server logs.";
  }
  return error.message;
}

function average(values) {
  const numericValues = values
    .filter((value) => value !== null && value !== undefined && value !== "")
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value));
  if (!numericValues.length) return null;
  return Math.round(numericValues.reduce((sum, value) => sum + value, 0) / numericValues.length);
}

function buildDashboardAnalytics(resumes, resumeDetails, templates) {
  const active = resumes.filter((resume) => resume.status !== "archived");
  const detailedResumes = active.map((resume) => resumeDetails[resume.id] || resume);
  const completedCount = active.filter((resume) => resume.status === "completed").length;
  const averageCompletion = average(active.map((resume) => resume.completion_percentage)) ?? 0;
  const averageAts = average(active.map((resume) => resume.ats_score));
  const downloadCount = active.reduce((sum, resume) => sum + Number(resume.download_count || 0), 0);
  const estimatedTokens = detailedResumes.reduce(
    (sum, resume) => sum + estimateResumeTokens(resume),
    0,
  );

  const roleCounts = countBy(
    active.map((resume) => resume.target_role || "No target role"),
  );
  const templateCounts = countBy(
    active.map((resume) => templateName(templates, resume.template_choice)),
  );
  const gaps = buildResumeGapCounts(detailedResumes);
  const readiness = buildReadinessAnalytics(active);
  const topResumes = active
    .filter((resume) => resume.ats_score !== null && resume.ats_score !== undefined && resume.ats_score !== "")
    .map((resume) => ({
      id: resume.id,
      title: resume.title || "Untitled Resume",
      score: clampPercentage(resume.ats_score),
    }))
    .sort((first, second) => second.score - first.score)
    .slice(0, 4);
  const resumeTokenCounts = detailedResumes.reduce((counts, resume) => {
    const title = resume.title || resume.target_role || "Untitled Resume";
    counts[title] = estimateResumeTokens(resume);
    return counts;
  }, {});

  return {
    summary: active.length
      ? `${active.length} active resume${active.length === 1 ? "" : "s"} tracked across ${Object.keys(roleCounts).length} target role${Object.keys(roleCounts).length === 1 ? "" : "s"}.`
      : "Create or import resumes to begin tracking readiness.",
    kpis: [
      {
        label: "Active resumes",
        value: active.length,
        detail: `${completedCount} completed`,
      },
      {
        label: "Avg completion",
        value: `${averageCompletion}%`,
        detail: "Across active resumes",
      },
      {
        label: "Avg ATS",
        value: averageAts === null ? "N/A" : `${averageAts}%`,
        detail: averageAts === null ? "Run ATS checks" : "Latest saved scores",
      },
      {
        label: "Exports",
        value: downloadCount,
        detail: "PDF downloads",
      },
      {
        label: "Resume tokens",
        value: formatNumber(estimatedTokens),
        detail: "Estimated content tokens",
      },
    ],
    roles: toBarItems(roleCounts, active.length),
    templates: toBarItems(templateCounts, active.length),
    tokens: toBarItems(resumeTokenCounts, Math.max(1, Math.max(...Object.values(resumeTokenCounts), 1))),
    gaps: toBarItems(gaps, Math.max(1, detailedResumes.length)),
    readiness,
    topResumes,
    actions: buildAnalyticsActions({
      averageAts,
      averageCompletion,
      gaps,
      hasActiveResumes: active.length > 0,
      topResumes,
    }),
  };
}

function buildReadinessAnalytics(resumes) {
  const scores = resumes.map((resume) => {
    const completion = clampPercentage(resume.completion_percentage);
    const ats = resume.ats_score === null || resume.ats_score === undefined || resume.ats_score === ""
      ? null
      : clampPercentage(resume.ats_score);
    // Completion remains the baseline until an ATS check is available.
    return ats === null ? completion : Math.round((completion + ats) / 2);
  });
  const bands = [
    { label: "Ready (80–100)", matches: (score) => score >= 80 },
    { label: "In progress (50–79)", matches: (score) => score >= 50 && score < 80 },
    { label: "Needs attention (0–49)", matches: (score) => score < 50 },
  ].map((band) => {
    const value = scores.filter(band.matches).length;
    return { ...band, value, percent: Math.round((value / Math.max(1, scores.length)) * 100) };
  });
  const score = average(scores) ?? 0;
  const scoredCount = resumes.filter((resume) => resume.ats_score !== null && resume.ats_score !== undefined && resume.ats_score !== "").length;

  return {
    score,
    scoredCount,
    bands,
    detail: scores.length
      ? `${bands[0].value} of ${scores.length} active resumes are ready to tailor and export.`
      : "Add a resume to start measuring readiness.",
  };
}

function estimateResumeTokens(resume) {
  const content = [
    resume.title,
    resume.target_role,
    resume.summary,
    resume.declaration,
    resume.personal_info?.name,
    resume.personal_info?.email,
    resume.personal_info?.phone,
    resume.personal_info?.location,
    ...(resume.skills ?? []).map((item) => item.skill_name || item),
    ...(resume.education ?? []).flatMap((item) => [
      item.school,
      item.degree,
      item.field,
      item.cgpa,
    ]),
    ...(resume.experience ?? []).flatMap((item) => [
      item.company,
      item.role,
      item.raw_input,
      ...(item.ai_generated_bullets ?? []),
    ]),
    ...(resume.projects ?? []).flatMap((item) => [
      item.title,
      item.description,
      item.technologies,
      ...(item.ai_generated_bullets ?? []),
    ]),
    ...(resume.certifications ?? []).flatMap((item) => [item.name, item.issuer]),
    ...(resume.publications ?? []).flatMap((item) => [item.title, item.description]),
    ...(resume.languages ?? []).flatMap((item) => [item.language_name, item.proficiency]),
    ...(resume.achievements ?? []).flatMap((item) => [item.title, item.description]),
  ]
    .filter(Boolean)
    .join(" ");
  if (!content.trim()) {
    return 0;
  }
  return Math.max(1, Math.ceil(content.length / 4));
}

function formatNumber(value) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

function buildResumeGapCounts(resumes) {
  const gapChecks = {
    "Missing summary": (resume) => !resume.summary?.trim(),
    "Missing skills": (resume) => (resume.skills?.length ?? 0) === 0,
    "Missing experience": (resume) => (resume.experience?.length ?? 0) === 0,
    "Missing education": (resume) => (resume.education?.length ?? 0) === 0,
    "Missing target role": (resume) => !resume.target_role?.trim(),
  };
  const gaps = {};
  for (const resume of resumes) {
    for (const [label, hasGap] of Object.entries(gapChecks)) {
      if (hasGap(resume)) {
        gaps[label] = (gaps[label] || 0) + 1;
      }
    }
  }
  return gaps;
}

function buildAnalyticsActions({ averageAts, averageCompletion, gaps, hasActiveResumes, topResumes }) {
  if (!hasActiveResumes) {
    return ["Create or import your first resume.", "Add a target role before generating AI content.", "Run an ATS check after entering core sections."];
  }
  const actions = [];
  if ((gaps["Missing target role"] || 0) > 0) {
    actions.push("Add target roles so AI summaries and ATS checks can tailor correctly.");
  }
  if ((gaps["Missing summary"] || 0) > 0) {
    actions.push("Generate or write focused summaries for resumes missing a professional summary.");
  }
  if ((gaps["Missing skills"] || 0) > 0) {
    actions.push("Add role-specific skills before exporting or checking ATS fit.");
  }
  if (averageCompletion < 80) {
    actions.push("Complete missing core sections to lift overall readiness.");
  }
  if (averageAts === null || topResumes.length === 0) {
    actions.push("Run ATS checks to identify the strongest resume versions.");
  } else if (averageAts < 75) {
    actions.push("Improve keyword coverage and evidence bullets on lower-scoring resumes.");
  }
  return actions.slice(0, 4);
}

function countBy(values) {
  return values.reduce((counts, value) => {
    const label = String(value || "Unknown").trim() || "Unknown";
    counts[label] = (counts[label] || 0) + 1;
    return counts;
  }, {});
}

function toBarItems(counts, total) {
  return Object.entries(counts)
    .map(([label, value]) => ({
      label,
      value,
      percent: Math.round((value / Math.max(1, total)) * 100),
    }))
    .sort((first, second) => second.value - first.value || first.label.localeCompare(second.label))
    .slice(0, 5);
}

function templateName(templates, templateId) {
  return templates.find((template) => template.id === templateId)?.name ?? templateId;
}

function initialsFor(title) {
  return String(title || "Resume")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function formatDateTime(value) {
  if (!value) {
    return "Not saved yet";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
