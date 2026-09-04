import { REQUIRED_SECTION_ORDER, SECTION_LABELS, normalizeResumeForTemplate, sectionHasContent } from "./resumeSchema.js";
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

function ResumeSection({ children, title }) {
  const hasChildren = Array.isArray(children) ? children.some(Boolean) : Boolean(children);
  if (!hasChildren) return null;
  return (
    <section className="resume-section">
      <h2>{title}</h2>
      {children}
    </section>
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
      <ResumeSection title={SECTION_LABELS.summary}>
        <p className="resume-summary">{resume.summary}</p>
      </ResumeSection>
    );
  }
  if (section === "declaration") {
    const text = resume.declaration ?? "I hereby declare that all the information provided above is true and correct to the best of my knowledge and belief.";
    if (!text || !text.trim()) return null;
    return (
      <ResumeSection title={SECTION_LABELS.declaration || "Declaration"}>
        <DeclarationBlock text={text} />
      </ResumeSection>
    );
  }
  if (section === "skills") {
    return (
      <ResumeSection title={SECTION_LABELS.skills}>
        {hasEntries(resume.skills) && (
          <div className="resume-skill-list">
            {resume.skills.map((item, i) => (
              <SkillItem key={`skill-${i}`} value={item.skill_name || item.name || item.value} />
            ))}
          </div>
        )}
      </ResumeSection>
    );
  }
  const items = resume[section] ?? [];
  return (
    <ResumeSection title={SECTION_LABELS[section] ?? titleize(section)}>
      {items.map((item, i) => (
        <SectionItem item={item} key={`${section}-${i}`} section={section} />
      ))}
    </ResumeSection>
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

export default function TraditionalProfessionalTemplate({ resume }) {
  const normalizedResume = normalizeResumeForTemplate(resume);
  const info = normalizedResume.personal_info ?? {};
  const role = normalizedResume.target_role;
  return (
    <div className="resume-page template-traditional-professional layout-single-column">
      <ResumeHeader info={info} role={role} />
      <div className="resume-content">
        <main className="resume-main">
          {renderSections(normalizedResume, REQUIRED_SECTION_ORDER)}
        </main>
      </div>
    </div>
  );
}
