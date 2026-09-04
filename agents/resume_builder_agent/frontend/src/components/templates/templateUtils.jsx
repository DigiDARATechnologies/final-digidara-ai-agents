export function contactLine(info) {
  return [info.email, info.phone, info.location].filter(Boolean).join(" | ");
}

export function contactItems(info) {
  return [info.email, info.phone, info.location].filter((item) => item && !isPlaceholder(item));
}

export function profileLinksLine(info) {
  return (info.links ?? [])
    .map((link) => displayProfileLink(link))
    .filter(Boolean)
    .join(" | ");
}

export function displayProfileLink(link) {
  const value = String(link || "").trim();
  if (!value || isPlaceholder(value)) {
    return "";
  }
  const labeledMatch = value.match(/^(github|linkedin|portfolio|website)\s*:\s*(.+)$/i);
  if (labeledMatch) {
    const label = labeledMatch[1].toLowerCase();
    const target = compactProfileTarget(labeledMatch[2]);
    const displayLabel =
      label === "github" ? "GitHub" :
      label === "linkedin" ? "LinkedIn" :
      label === "website" ? "Website" :
      "Portfolio";
    return target ? `${displayLabel}: ${target}` : displayLabel;
  }
  const cleanValue = value.replace(/^https?:\/\//i, "").replace(/^www\./i, "").replace(/\/$/, "");
  if (/github\.com/i.test(cleanValue)) {
    const profile = cleanValue.split("github.com/")[1]?.split(/[/?#]/)[0];
    return profile ? `GitHub: ${profile}` : "GitHub";
  }
  if (/linkedin\.com/i.test(cleanValue)) {
    const profile = cleanValue.split("linkedin.com/")[1]?.replace(/^in\//, "").split(/[/?#]/)[0];
    return profile ? `LinkedIn: ${profile}` : "LinkedIn";
  }
  if (/^(github|linkedin|portfolio|website)\s*:/i.test(value)) {
    return value;
  }
  return `Portfolio: ${cleanValue}`;
}

function compactProfileTarget(value) {
  const cleanValue = String(value || "")
    .trim()
    .replace(/^https?:\/\//i, "")
    .replace(/^www\./i, "")
    .replace(/\/$/, "");
  if (!cleanValue || isPlaceholder(cleanValue) || cleanValue === "github.com" || cleanValue === "linkedin.com") {
    return "";
  }
  if (/github\.com/i.test(cleanValue)) {
    return cleanValue.split("github.com/")[1]?.split(/[/?#]/)[0] || "";
  }
  if (/linkedin\.com/i.test(cleanValue)) {
    return cleanValue.split("linkedin.com/")[1]?.replace(/^in\//, "").split(/[/?#]/)[0] || "";
  }
  return cleanValue;
}

export function profileLinkHref(link) {
  const value = String(link || "").trim();
  if (!value || isPlaceholder(value)) {
    return "";
  }
  const labeledMatch = value.match(/^(github|linkedin|portfolio|website)\s*:\s*(.+)$/i);
  let target = (labeledMatch ? labeledMatch[2] : value).trim().replace(/[.,;\s]+$/, "");
  if (!target || isPlaceholder(target) || target.toLowerCase() === "github.com" || target.toLowerCase() === "linkedin.com") {
    return "";
  }
  const candidate = /^https?:\/\//i.test(target) ? target : `https://${target.replace(/^www\./i, "")}`;
  try {
    const url = new URL(candidate);
    if ((url.protocol === "http:" || url.protocol === "https:") && url.hostname.includes(".")) {
      return url.href;
    }
  } catch (err) {
    return "";
  }
  return "";
}

// Renders a profile link (GitHub/LinkedIn/portfolio/website) as a real clickable
// anchor when it resolves to a valid URL, falling back to plain text otherwise.
export function ProfileLinkItem({ link }) {
  const label = displayProfileLink(link);
  if (!label) {
    return null;
  }
  const href = profileLinkHref(link);
  if (!href) {
    return <span>{label}</span>;
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {label}
    </a>
  );
}

export function isPlaceholder(value) {
  return /\[\s*add\b/i.test(String(value || ""));
}

export function dateRange(startDate, endDate) {
  if (!startDate && !endDate) {
    return "";
  }
  return [startDate, endDate].filter(Boolean).map(compactResumeDate).join(" – ");
}

function compactResumeDate(value) {
  const date = String(value ?? "").trim().replace(/\s+/g, " ");
  const isoMatch = date.match(/^(\d{4})-(\d{2})(?:-\d{2})?$/);
  if (isoMatch) {
    const monthIndex = Number(isoMatch[2]) - 1;
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return months[monthIndex] ? `${months[monthIndex]} ${isoMatch[1]}` : date;
  }
  return date.replace(/\b(January|February|March|April|May|June|July|August|September|October|November|December)\b/gi, (month) => month.slice(0, 3));
}

export function hasEntries(items) {
  return Array.isArray(items) && items.length > 0;
}

// SkillItem component used by multiple templates
export function SkillItem({ value }) {
  if (!value || isPlaceholder(value)) {
    return null;
  }
  const [label, details] = String(value || "").split(/:\s(.+)/);
  if (!details) {
    return <span className="resume-skill">{value}</span>;
  }
  return (
    <p className="resume-skill grouped">
      <strong>{label}</strong>
      <span>{details}</span>
    </p>
  );
}

export function DeclarationBlock({ text }) {
  const lines = String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const detailStart = lines.findIndex((line) => /^(place|date|signature)\s*:/i.test(line));
  const statementLines = detailStart >= 0 ? lines.slice(0, detailStart) : lines;
  const detailLines = detailStart >= 0 ? lines.slice(detailStart) : [];

  return (
    <div className="resume-declaration">
      {statementLines.length > 0 && (
        <p className="resume-declaration-text">{statementLines.join(" ")}</p>
      )}
      {detailLines.length > 0 && (
        <div className="resume-declaration-details">
          {detailLines.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      )}
    </div>
  );
}

export function titleize(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function splitProjectDescription(description, aiGeneratedBullets = []) {
  const lines = String(description || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const meta = [];
  const bullets = [];

  for (const line of lines) {
    if (/^(technologies|tech stack|tools used)\s*:/i.test(line)) {
      meta.push(line);
    } else if (/^(github|live demo|demo|link|url)\s*:/i.test(line)) {
      bullets.push(line);
    } else {
      bullets.push(line.replace(/^[*-]\s*/, ""));
    }
  }

  return {
    meta: meta.join(" | "),
    body: aiGeneratedBullets.length ? "" : (lines.length ? "" : description),
    bullets: aiGeneratedBullets.length ? aiGeneratedBullets : bullets,
  };
}

export function ExperienceItem({ item }) {
  return (
    <ResumeItem
      body={item.ai_generated_bullets?.length ? "" : item.raw_input}
      bullets={item.ai_generated_bullets}
      dates={dateRange(item.start_date, item.end_date)}
      meta={item.company}
      title={item.role}
    />
  );
}

export function ResumeItem({ body, bullets = [], dates, meta, title }) {
  const cleanTitle = isPlaceholder(title) ? "" : title;
  const cleanMeta = isPlaceholder(meta) ? "" : meta;
  const cleanBody = isPlaceholder(body) ? "" : body;
  const cleanBullets = (bullets ?? []).filter((bullet) => bullet && !isPlaceholder(bullet));
  if (!cleanTitle && !cleanMeta && !cleanBody && !cleanBullets.length) {
    return null;
  }
  return (
    <article className="resume-item">
      <div className="resume-item-header">
        <div className="resume-item-primary">
          {cleanTitle && <h3 className={sectionClassName(cleanTitle)}>{cleanTitle}</h3>}
          {cleanMeta && <p>{cleanMeta}</p>}
        </div>
        {dates && <div className="resume-item-meta">{dates}</div>}
      </div>
      {cleanBody && <p className="resume-item-body">{cleanBody}</p>}
      {cleanBullets.length > 0 && (
        <ul className="resume-bullets">
          {cleanBullets.map((bullet, index) => (
            <li key={`bullet-${index}`}>{bullet}</li>
          ))}
        </ul>
      )}
    </article>
  );
}

function sectionClassName(value) {
  const lowered = String(value || "").toLowerCase();
  if (lowered.includes("project")) return "resume-project-title";
  return "resume-entry-title";
}
