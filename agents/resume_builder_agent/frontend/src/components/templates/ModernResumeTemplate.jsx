import { SECTION_LABELS, normalizeResumeForTemplate, sectionHasContent } from "./resumeSchema.js";
import { contactItems, displayProfileLink, ProfileLinkItem, hasEntries, dateRange, splitProjectDescription, titleize, ExperienceItem, ResumeItem, SkillItem, DeclarationBlock } from "./templateUtils.jsx";

const MAIN_SECTIONS = ["summary", "experience", "projects", "publications", "achievements", "declaration"];
const SIDE_SECTIONS = ["education", "skills", "certifications", "languages"];

function Section({ resume, section }) {
  if (!sectionHasContent(section, resume)) return null;
  if (section === "summary") return <section className="section"><h2>{SECTION_LABELS.summary}</h2><p className="resume-summary">{resume.summary}</p></section>;
  if (section === "skills") return <section className="section"><h2>{SECTION_LABELS.skills}</h2>{hasEntries(resume.skills) && <div className="skill-list">{resume.skills.map((item, index) => <SkillItem key={`skill-${index}`} value={item.skill_name || item.name || item.value} />)}</div>}</section>;
  if (section === "declaration") return resume.declaration?.trim() ? <section className="section"><h2>{SECTION_LABELS.declaration}</h2><DeclarationBlock text={resume.declaration} /></section> : null;
  const items = Array.isArray(resume[section]) ? resume[section] : [];
  return <section className="section"><h2>{SECTION_LABELS[section] ?? titleize(section)}</h2>{items.map((item, index) => <Entry key={`${section}-${index}`} item={item} section={section} />)}</section>;
}

function Entry({ item, section }) {
  if (["experience", "internships", "research_experience"].includes(section)) return <ExperienceItem item={item} />;
  if (section === "education") return <ResumeItem title={item.school} meta={[item.degree, item.field, item.cgpa && `CGPA: ${item.cgpa}`].filter(Boolean).join(", ")} dates={dateRange(item.start_date, item.end_date)} />;
  if (section === "projects") { const project = splitProjectDescription(item.description, item.ai_generated_bullets); return <ResumeItem title={item.title || item.name} meta={project.meta} body={project.body} bullets={project.bullets} />; }
  if (section === "languages") return <ResumeItem title={item.language_name || item.name} meta={item.proficiency} />;
  return <ResumeItem title={item.name || item.title || item.role} meta={item.issuer || item.organization || item.publisher} body={item.description || item.details} dates={item.date || dateRange(item.start_date, item.end_date)} />;
}

export default function ModernResumeTemplate({ resume, variant, twoColumn = false }) {
  const normalized = normalizeResumeForTemplate(resume);
  const info = normalized.personal_info ?? {};
  const links = (info.links ?? []).filter(link => displayProfileLink(link));
  const main = <main className="resume-main">{MAIN_SECTIONS.map(section => <Section key={section} resume={normalized} section={section} />)}</main>;
  const side = <aside className="sidebar">{SIDE_SECTIONS.map(section => <Section key={section} resume={normalized} section={section} />)}</aside>;
  return <div className={`resume-page template-${variant} layout-${twoColumn ? "two-column" : "single-column"}`}>
    <header className="resume-header"><div className="resume-identity"><h1 className="resume-name">{info.name || "Your Name"}</h1>{normalized.target_role && <p className="resume-role">{normalized.target_role}</p>}</div><div className="resume-contact">{contactItems(info).map(item => <span key={item}>{item}</span>)}{links.map(link => <ProfileLinkItem key={link} link={link} />)}</div></header>
    <div className="resume-content">{twoColumn ? <div className="resume-body">{main}{side}</div> : <>{main}{side}</>}</div>
  </div>;
}
