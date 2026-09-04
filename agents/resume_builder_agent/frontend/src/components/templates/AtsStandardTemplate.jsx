import { REQUIRED_SECTION_ORDER, SECTION_LABELS, normalizeResumeForTemplate, sectionHasContent } from "./resumeSchema.js";
import { contactItems, displayProfileLink, ProfileLinkItem, hasEntries, dateRange, splitProjectDescription, titleize, ExperienceItem, ResumeItem, SkillItem, DeclarationBlock } from "./templateUtils.jsx";

function Section({ resume, section }) {
  if (!sectionHasContent(section, resume)) return null;
  if (section === "summary") return <section className="section"><h2>{SECTION_LABELS.summary}</h2><p className="resume-summary">{resume.summary}</p></section>;
  if (section === "skills") return <section className="section"><h2>{SECTION_LABELS.skills}</h2>{hasEntries(resume.skills) && <div className="skill-list">{resume.skills.map((item, index) => <SkillItem key={index} value={item.skill_name || item.name || item.value} />)}</div>}</section>;
  if (section === "declaration") return resume.declaration?.trim() ? <section className="section"><h2>{SECTION_LABELS.declaration}</h2><DeclarationBlock text={resume.declaration} /></section> : null;
  const items = Array.isArray(resume[section]) ? resume[section] : [];
  return <section className="section"><h2>{SECTION_LABELS[section] ?? titleize(section)}</h2>{items.map((item, index) => <Entry item={item} key={`${section}-${index}`} section={section} />)}</section>;
}

function Entry({ item, section }) {
  if (["experience", "internships", "research_experience"].includes(section)) return <ExperienceItem item={item} />;
  if (section === "education") return <ResumeItem dates={dateRange(item.start_date, item.end_date)} meta={[item.degree, item.field, item.cgpa && `CGPA: ${item.cgpa}`].filter(Boolean).join(", ")} title={item.school} />;
  if (section === "projects") { const project = splitProjectDescription(item.description, item.ai_generated_bullets); return <ResumeItem body={project.body} bullets={project.bullets} meta={project.meta} title={item.title || item.name} />; }
  if (section === "languages") return <ResumeItem meta={item.proficiency} title={item.language_name || item.name} />;
  return <ResumeItem body={item.description || item.details} dates={item.date || dateRange(item.start_date, item.end_date)} meta={item.issuer || item.organization || item.publisher} title={item.name || item.title || item.role} />;
}

export default function AtsStandardTemplate({ resume }) {
  const data = normalizeResumeForTemplate(resume);
  const info = data.personal_info || {};
  const links = (info.links || []).filter(displayProfileLink);
  return <div className="resume-page template-ats-standard layout-single-column">
    <header className="resume-header">
      <h1 className="resume-name">{info.name || "Your Name"}</h1>
      {data.target_role && <p className="resume-role">{data.target_role}</p>}
      <div className="resume-contact">{contactItems(info).map((item) => <span key={item}>{item}</span>)}{links.map((link) => <ProfileLinkItem key={link} link={link} />)}</div>
    </header>
    <main className="resume-main">{REQUIRED_SECTION_ORDER.map((section) => <Section key={section} resume={data} section={section} />)}</main>
  </div>;
}
