import { SECTION_LABELS, normalizeResumeForTemplate, sectionHasContent } from "./resumeSchema.js";
import { contactItems, displayProfileLink, ProfileLinkItem, hasEntries, dateRange, splitProjectDescription, titleize, ExperienceItem, ResumeItem, SkillItem, DeclarationBlock } from "./templateUtils.jsx";

function ResumeHeader({ info, role }) {
  const links = (info.links ?? []).filter(link => displayProfileLink(link));
  return (
    <header className="resume-header">
      <div className="resume-identity">
        <h1 className="resume-name">{info.name || "Your Name"}</h1>
        {role && <p className="resume-role">{role}</p>}
      </div>
      <div className="resume-contact resume-contact-list">
        {contactItems(info).map(item => (
          <span key={item}>{item}</span>
        ))}
        {links.map(link => (
          <ProfileLinkItem key={link} link={link} />
        ))}
      </div>
    </header>
  );
}

const MAIN_SECTION_ORDER = ["summary", "experience", "publications", "declaration"];
const SIDEBAR_SECTION_ORDER = ["education", "skills", "certifications", "languages"];

function Sidebar({ resume }) {
  return (
    <aside className="sidebar">
      {renderSections(resume, SIDEBAR_SECTION_ORDER)}
    </aside>
  );
}

function renderSections(resume, sectionIds) {
  return sectionIds
    .filter(section => sectionHasContent(section, resume))
    .map(section => (
      <TemplateSection resume={resume} section={section} key={section} />
    ));
}

function TemplateSection({ resume, section }) {
  if (section === "summary") {
    return (
      <section className="main-section">
        <h2>{SECTION_LABELS.summary}</h2>
        <p className="resume-summary">{resume.summary}</p>
      </section>
    );
  }
  if (section === "declaration") {
    const text = resume.declaration ?? "";
    if (!text.trim()) return null;
    return (
      <section className="main-section">
        <h2>{SECTION_LABELS.declaration}</h2>
        <DeclarationBlock text={text} />
      </section>
    );
  }
  if (section === "skills") {
    return (
      <section className="main-section">
        <h2>{SECTION_LABELS.skills}</h2>
        {hasEntries(resume.skills) && (
          <div className="sidebar-skill-list">
            {resume.skills.map((item, i) => (
              <SkillItem key={`skill-${i}`} value={item.skill_name || item.name || item.value} />
            ))}
          </div>
        )}
      </section>
    );
  }
  const items = Array.isArray(resume[section]) ? resume[section] : [];
  return (
    <section className="main-section">
      <h2>{SECTION_LABELS[section] ?? titleize(section)}</h2>
      {items.map((item, i) => (
        <SectionItem item={item} key={`${section}-${i}`} section={section} />
      ))}
    </section>
  );
}

function SectionItem({ item, section }) {
  if (["experience", "internships", "research_experience"].includes(section)) {
    return <ExperienceItem item={item} />;
  }
  if (section === "education") {
    return (
      <ResumeItem
        dates={dateRange(item.start_date, item.end_date)}
        meta={[item.degree, item.field, item.cgpa && `CGPA: ${item.cgpa}`].filter(Boolean).join(", ")}
        title={item.school}
      />
    );
  }
  if (["certifications", "courses", "training"].includes(section)) {
    return (
      <ResumeItem
        dates={item.date || item.end_date}
        meta={item.issuer || item.provider || item.organization}
        title={item.name || item.title}
      />
    );
  }
  if (section === "languages") {
    return <ResumeItem meta={item.proficiency} title={item.language_name || item.name} />;
  }
  if (section === "projects") {
    const project = splitProjectDescription(item.description, item.ai_generated_bullets);
    return (
      <ResumeItem body={project.body} bullets={project.bullets} meta={project.meta} title={item.title || item.name} />
    );
  }
  return (
    <ResumeItem
      body={item.description || item.summary || item.details}
      dates={item.date || dateRange(item.start_date, item.end_date)}
      meta={item.organization || item.publisher || item.issuer || item.technologies}
      title={item.title || item.name || item.role}
    />
  );
}

export default function ExecutiveSidebarTemplate({ resume }) {
  const normalized = normalizeResumeForTemplate(resume);
  const info = normalized.personal_info ?? {};
  const role = normalized.target_role;
  return (
    <div className="resume-page template-executive-sidebar layout-two-column">
      <ResumeHeader info={info} role={role} />
      <div className="resume-body">
        <main className="resume-main">
          {renderSections(normalized, MAIN_SECTION_ORDER)}
        </main>
        <Sidebar resume={normalized} />
      </div>
    </div>
  );
}
