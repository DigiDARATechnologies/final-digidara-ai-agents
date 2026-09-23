export const TEMPLATE_REGISTRY = [
  {
    id: "ats-standard",
    name: "ATS Standard",
    category: "ATS",
    layout: "single-column",
    atsLevel: "very-high",
    supportsPhoto: false,
    defaultColor: "#1f2937",
    description: "Strict one-column ATS layout: standard headings, real text, no photo, sidebar, tables, or graphics.",
    recommendedFor: ["All roles", "Online applications", "Strict ATS portals"],
    themes: ["ATS", "Plain text", "Single column"],
  },
  {
    id: "steady-form",
    name: "Precision ATS",
    category: "ATS",
    layout: "single-column",
    atsLevel: "high",
    supportsPhoto: false,
    defaultColor: "#1f2937",
    description: "A compact single-column layout optimized for fast ATS parsing and precise alignment.",
    recommendedFor: ["Data Analysts", "Engineers", "Technical Roles"],
    themes: ["Monochrome", "ATS"],
  },
  {
    id: "classic-serif",
    name: "Heritage Serif",
    category: "Professional",
    layout: "single-column",
    atsLevel: "very-high",
    supportsPhoto: false,
    defaultColor: "#111111",
    description: "A timeless black-and-white serif resume with formal rules and generous readability.",
    recommendedFor: ["Consultants", "Business", "General Professional"],
    themes: ["Serif", "Black & White"],
  },
  {
    id: "mercury-flow",
    name: "Modern Halo",
    category: "Modern",
    layout: "single-column",
    atsLevel: "high",
    supportsPhoto: false,
    defaultColor: "#d9dcd7",
    description: "A contemporary single-column resume with a soft header and balanced visual rhythm.",
    recommendedFor: ["Sales", "Customer Success", "Product Roles"],
    themes: ["Soft Gray", "Modern"],
  },
  {
    id: "slate-dawn",
    name: "Executive Slate",
    category: "Executive",
    layout: "two-column",
    atsLevel: "high",
    supportsPhoto: false,
    defaultColor: "#29224a",
    description: "A distinctive two-column executive resume with a slate banner and editorial hierarchy.",
    recommendedFor: ["Leadership", "Management", "Communications"],
    themes: ["Slate", "Serif"],
  },
  {
    id: "minimalist-line",
    name: "Minimalist Line",
    category: "Minimal",
    layout: "single-column",
    atsLevel: "high",
    supportsPhoto: false,
    defaultColor: "#334155",
    description: "A restrained one-column layout with a clean left-aligned hierarchy and generous whitespace.",
    recommendedFor: ["Early Career", "Technical Roles", "General Professional"],
    themes: ["Minimal", "Clean"],
  },
  {
    id: "sidebar-focus",
    name: "Sidebar Focus",
    category: "Modern",
    layout: "two-column",
    atsLevel: "high",
    supportsPhoto: false,
    defaultColor: "#0f766e",
    description: "A practical teal sidebar layout for skills, contact details, and core experience.",
    recommendedFor: ["Product", "Design", "Customer Success"],
    themes: ["Sidebar", "Teal"],
  },
  {
    id: "compact-impact",
    name: "Compact Impact",
    category: "ATS",
    layout: "single-column",
    atsLevel: "very-high",
    supportsPhoto: false,
    defaultColor: "#1d4ed8",
    description: "A concise, accomplishment-led one-page layout for compact resumes.",
    recommendedFor: ["Consultants", "Analysts", "One-page Resumes"],
    themes: ["Compact", "ATS"],
  },
  {
    id: "studio-bold",
    name: "Studio Bold",
    category: "Creative",
    layout: "single-column",
    atsLevel: "high",
    supportsPhoto: false,
    defaultColor: "#be123c",
    description: "A bold left-aligned layout for marketing, brand, and creative professionals.",
    recommendedFor: ["Marketing", "Creative", "Brand Roles"],
    themes: ["Bold", "Creative"],
  },
  {
    id: "timeline-teal",
    name: "Timeline Teal",
    category: "Modern",
    layout: "two-column",
    atsLevel: "high",
    supportsPhoto: false,
    defaultColor: "#0f766e",
    description: "A calm teal sidebar paired with a clear accomplishment timeline.",
    recommendedFor: ["Product Managers", "Operations", "Customer Success"],
    themes: ["Timeline", "Teal"],
  },
  {
    id: "sidebar-mono", name: "Sidebar Mono", category: "Minimal", layout: "two-column", atsLevel: "high", supportsPhoto: false,
    defaultColor: "#334155", description: "A crisp monochrome sidebar with restrained editorial spacing.", recommendedFor: ["Developers", "Analysts", "Early Career"], themes: ["Monochrome", "Sidebar"],
  },
  { id: "horizon-coral", name: "Horizon Coral", category: "Creative", layout: "single-column", atsLevel: "high", supportsPhoto: false, defaultColor: "#e76f51", description: "A warm color-block header with a spacious single-column reading flow.", recommendedFor: ["Marketing", "Design", "Communications"], themes: ["Coral", "Editorial"] },
  { id: "ledger-navy", name: "Ledger Navy", category: "Professional", layout: "single-column", atsLevel: "very-high", supportsPhoto: false, defaultColor: "#1e3a5f", description: "A precise navy ledger with compact dividers and focused hierarchy.", recommendedFor: ["Finance", "Consulting", "Business"], themes: ["Navy", "Structured"] },
  { id: "split-olive", name: "Split Olive", category: "Modern", layout: "two-column", atsLevel: "high", supportsPhoto: false, defaultColor: "#556b2f", description: "An earthy split layout that separates evidence from credentials.", recommendedFor: ["Sustainability", "Operations", "Research"], themes: ["Olive", "Split" ] },
  { id: "canvas-sand", name: "Canvas Sand", category: "Minimal", layout: "single-column", atsLevel: "high", supportsPhoto: false, defaultColor: "#a16207", description: "A soft sand header with understated, highly readable sections.", recommendedFor: ["General Professional", "Education", "Nonprofit"], themes: ["Sand", "Minimal"] },
  { id: "column-indigo", name: "Column Indigo", category: "Executive", layout: "two-column", atsLevel: "high", supportsPhoto: false, defaultColor: "#4338ca", description: "A confident indigo sidebar for leadership stories and core strengths.", recommendedFor: ["Leadership", "Product", "Strategy"], themes: ["Indigo", "Column"] },
  { id: "arc-slate", name: "Arc Slate", category: "ATS", layout: "single-column", atsLevel: "very-high", supportsPhoto: false, defaultColor: "#475569", description: "A slate-gray ATS layout with clean rules and compact evidence blocks.", recommendedFor: ["Engineering", "Analytics", "Technical Roles"], themes: ["Slate", "ATS"] },
  { id: "pulse-rose", name: "Pulse Rose", category: "Creative", layout: "two-column", atsLevel: "high", supportsPhoto: false, defaultColor: "#be185d", description: "A rose-accented two-column composition with an energetic but professional rhythm.", recommendedFor: ["Brand", "Marketing", "People Operations"], themes: ["Rose", "Contemporary"] },
  { id: "signal-amber", name: "Signal Amber", category: "Modern", layout: "single-column", atsLevel: "high", supportsPhoto: false, defaultColor: "#b45309", description: "A bold amber title band that keeps the resume content calm and scannable.", recommendedFor: ["Sales", "Growth", "Customer Success"], themes: ["Amber", "Bold"] },
  { id: "navy-portrait", name: "Navy Portrait", category: "Professional", layout: "single-column", atsLevel: "high", supportsPhoto: true, defaultColor: "#13233a", description: "A navy header with timeline entries, skill columns, and language proficiency dots.", recommendedFor: ["Analysts", "Engineers", "Business Professionals"], themes: ["Navy", "Photo", "Structured"] },
];

export const REQUIRED_SECTION_ORDER = [
  "summary",
  "experience",
  "projects",
  "education",
  "skills",
  "publications",
  "certifications",
  "languages",
  "achievements",
  "declaration",
];

export const DEFAULT_SECTION_ORDER = [
  ...REQUIRED_SECTION_ORDER,
  "projects",
  "achievements",
  "internships",
  "training",
  "courses",
  "research_experience",
  "conferences",
  "volunteering",
  "professional_memberships",
  "open_source_contributions",
  "references",
  "custom_sections",
];

export const SECTION_LABELS = {
  summary: "Professional Summary",
  declaration: "Declaration",
  education: "Education",
  skills: "Technical Skills",
  experience: "Experience",
  projects: "Projects",
  certifications: "Certifications",
  publications: "Publications",
  achievements: "Achievements",
  languages: "Languages",
  internships: "Internships",
  training: "Training",
  courses: "Courses",
  research_experience: "Research Experience",
  conferences: "Conferences",
  volunteering: "Volunteering",
  professional_memberships: "Professional Memberships",
  open_source_contributions: "Open-Source Contributions",
  references: "References",
  custom_sections: "Custom Sections",
};

export function getTargetRole(resume = {}) {
  const value =
    resume.targetRole ??
    resume.target_role ??
    resume.targetJobTitle ??
    resume.target_job_title ??
    resume.role ??
    resume.jobTitle ??
    "";

  return typeof value === "string" ? value.trim() : "";
}

export const DEFAULT_DECLARATION =
  "I hereby declare that the information provided in this resume is true and accurate to the best of my knowledge and belief.";

export function normalizeResumeForTemplate(resume = {}) {
  const hiddenSections = new Set(resume.hidden_sections ?? []);
  const savedOrder = Array.isArray(resume.section_order) ? resume.section_order : [];
  const sectionOrder = Array.from(new Set([
    ...savedOrder.filter((section) => DEFAULT_SECTION_ORDER.includes(section)),
    ...DEFAULT_SECTION_ORDER.filter((section) => !savedOrder.includes(section)),
  ]));

  const canonicalRole = getTargetRole(resume);

  return {
    ...resume,
    targetRole: canonicalRole,
    target_role: canonicalRole,
    personal_info: resume.personal_info ?? {},
    summary: resume.summary ?? "",
    declaration: resume.declaration ?? DEFAULT_DECLARATION,
    declaration_enabled: resume.declaration_enabled !== undefined ? Boolean(resume.declaration_enabled) : (resume.declaration !== null && resume.declaration !== undefined ? Boolean(String(resume.declaration).trim()) : true),
    skills: normalizeCollection(resume.skills),
    experience: normalizeCollection(resume.experience),
    education: normalizeCollection(resume.education),
    projects: normalizeCollection(resume.projects),
    certifications: normalizeCollection(resume.certifications),
    publications: normalizeCollection(resume.publications),
    achievements: normalizeCollection(resume.achievements),
    languages: normalizeCollection(resume.languages),
    internships: normalizeCollection(resume.internships),
    training: normalizeCollection(resume.training),
    courses: normalizeCollection(resume.courses),
    research_experience: normalizeCollection(resume.research_experience),
    conferences: normalizeCollection(resume.conferences),
    volunteering: normalizeCollection(resume.volunteering),
    professional_memberships: normalizeCollection(resume.professional_memberships),
    open_source_contributions: normalizeCollection(resume.open_source_contributions),
    references: normalizeCollection(resume.references),
    custom_sections: normalizeCollection(resume.custom_sections),
    section_order: sectionOrder,
    hidden_sections: hiddenSections,
  };
}

export function sectionHasContent(section, resume) {
  if (resume.hidden_sections?.has(section)) {
    return false;
  }
  if (section === "summary") {
    return Boolean(resume.summary?.trim());
  }
  if (section === "declaration") {
    const isEnabled = resume.declaration_enabled !== false;
    if (!isEnabled) return false;
    const text = resume.declaration ?? "";
    return Boolean(text && text.trim() && !isPlaceholderValue(text));
  }
  if (section === "skills") {
    return normalizeCollection(resume.skills).some((item) => {
      const value = item.skill_name || item.name || item.value;
      return value && !isPlaceholderValue(value);
    });
  }
  return normalizeCollection(resume[section]).some((item) =>
    Object.entries(item).some(([key, value]) => {
      if (["id", "resume_id"].includes(key)) return false;
      if (Array.isArray(value)) return value.length > 0;
      return Boolean(String(value ?? "").trim()) && !isPlaceholderValue(value);
    }),
  );
}

function normalizeCollection(value) {
  return Array.isArray(value) ? value : [];
}

function isPlaceholderValue(value) {
  const str = String(value || "").trim();
  if (!str) return true;
  if (/^(none|null|n\/a|undefined)$/i.test(str)) return true;
  if (/^\[.*\]$/.test(str)) return true;
  return /\[\s*add\b/i.test(str);
}
