import { normalizeResumeForTemplate } from "./resumeSchema.js";
import { dateRange, displayProfileLink, splitProjectDescription, DeclarationBlock } from "./templateUtils.jsx";

function proficiencyDots(value) {
  const level = String(value || "").toLowerCase();
  const filled = /native|fluent|advanced/.test(level) ? 5 : /intermediate/.test(level) ? 4 : /basic|beginner/.test(level) ? 2 : 3;
  return `${"\u25cf".repeat(filled)}${"\u25cb".repeat(5 - filled)}`;
}

function Section({ title, children }) {
  return children ? <section className="navy-portrait-section"><h2>{title}</h2>{children}</section> : null;
}

function TimelineEntry({ item, project = false }) {
  const details = project ? splitProjectDescription(item.description, item.ai_generated_bullets) : null;
  const bullets = project ? details.bullets : (item.ai_generated_bullets?.length ? item.ai_generated_bullets : [item.raw_input].filter(Boolean));
  const title = project ? (item.title || item.name) : item.company;
  const subtitle = project ? details.meta : item.role;
  const dates = dateRange(item.start_date, item.end_date) || item.date;
  if (!title && !subtitle && !dates && !bullets?.length) return null;
  return <article className="navy-portrait-entry">
    <div className="navy-portrait-date">{dates}{item.location && <small>{item.location}</small>}</div>
    <div className="navy-portrait-entry-copy">
      {title && <h3>{title}</h3>}
      {subtitle && <p>{subtitle}</p>}
      {bullets?.length > 0 && <ul>{bullets.map((bullet, index) => <li key={index}>{bullet}</li>)}</ul>}
    </div>
  </article>;
}

export default function NavyPortraitTemplate({ resume }) {
  const data = normalizeResumeForTemplate(resume);
  const info = data.personal_info || {};
  const skills = data.skills.map((item) => item.skill_name || item.name || item.value).filter(Boolean);
  const links = (info.links || []).map(displayProfileLink).filter(Boolean);
  const tagline = [data.target_role, ...skills.slice(0, 3)].filter(Boolean).join(" \u2022 ");
  const photoUrl = data.profile_photo && data.id ? `/api/resume/${data.id}/photo` : "";

  return <div className="resume-page template-navy-portrait layout-single-column">
    <header className="navy-portrait-header">
      {photoUrl && <img alt="Profile portrait" className="navy-portrait-photo" src={photoUrl} />}
      <div className="navy-portrait-identity">
        <h1>{info.name || "Your Name"}</h1>
        {tagline && <p>{tagline}</p>}
        <div className="navy-portrait-contact-row"><span>{info.email}</span><span>{info.phone}</span></div>
        <div className="navy-portrait-contact-row"><span>{info.location}</span>{links.map((link) => <span key={link}>{link}</span>)}</div>
      </div>
    </header>
    <main className="navy-portrait-content">
      <Section title="PROFILE">{data.summary && <p className="navy-portrait-summary">{data.summary}</p>}</Section>
      <Section title="PROFESSIONAL EXPERIENCE">{data.experience.length > 0 && data.experience.map((item, index) => <TimelineEntry key={index} item={item} />)}</Section>
      <Section title="EDUCATION">{data.education.length > 0 && data.education.map((item, index) => <TimelineEntry key={index} item={{ title: item.school, date: dateRange(item.start_date, item.end_date), description: [item.degree, item.field, item.cgpa && `CGPA: ${item.cgpa}`].filter(Boolean).join(" | ") }} project />)}</Section>
      <Section title="SKILLS">{skills.length > 0 && <ul className="navy-portrait-skills">{skills.map((skill, index) => <li key={index}>{skill}</li>)}</ul>}</Section>
      <Section title="LANGUAGES">{data.languages.length > 0 && <div className="navy-portrait-languages">{data.languages.map((item, index) => <span key={index}>{item.language_name || item.name}<b aria-label={item.proficiency || "proficient"}>{proficiencyDots(item.proficiency)}</b></span>)}</div>}</Section>
      <Section title="PROJECTS">{data.projects.length > 0 && data.projects.map((item, index) => <TimelineEntry key={index} item={item} project />)}</Section>
      <Section title="INTERESTS">{data.achievements.length > 0 && data.achievements.map((item, index) => <TimelineEntry key={index} item={item} project />)}</Section>
      <Section title="CERTIFICATES">{data.certifications.length > 0 && data.certifications.map((item, index) => <TimelineEntry key={index} item={{ title: item.name, date: item.date, description: item.issuer }} project />)}</Section>
      <Section title="PUBLICATIONS">{data.publications.length > 0 && data.publications.map((item, index) => <TimelineEntry key={index} item={item} project />)}</Section>
      {data.declaration_enabled !== false && Boolean(data.declaration?.trim()) && (
        <Section title="DECLARATION">
          <DeclarationBlock text={data.declaration} />
        </Section>
      )}
    </main>
  </div>;
}
