export const SKILL_CATEGORIES = [
  "Programming Languages",
  "Data Analytics",
  "Databases",
  "Machine Learning",
  "Visualization and BI",
  "Frameworks",
  "AI and LLM Tools",
  "Cloud and Deployment",
  "Business and Soft Skills",
];

export function cleanBulletText(value) {
  return String(value || "")
    .replace(/^[\s•\-*]+/, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function normalizeBulletList(values = []) {
  return (Array.isArray(values) ? values : [values])
    .map((item) => {
      if (typeof item === "string") return cleanBulletText(item);
      if (item && typeof item === "object") return cleanBulletText(item.text || item.content || item.value);
      return "";
    })
    .filter(Boolean)
    .filter((item, index, items) => items.findIndex((candidate) => candidate.toLowerCase() === item.toLowerCase()) === index);
}

export function splitSkillText(value) {
  return String(value || "")
    .split(",")
    .map((item) => normalizeSkillName(item))
    .filter(Boolean);
}

export function normalizeSkillName(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b([a-z])/g, (match) => match.toUpperCase());
}

export function skillsToCategories(skills = []) {
  const categories = Object.fromEntries(SKILL_CATEGORIES.map((category) => [category, []]));
  const uncategorized = [];

  for (const item of Array.isArray(skills) ? skills : []) {
    const value = typeof item === "string" ? item : item?.skill_name || item?.name || item?.value || "";
    if (!value) continue;
    const [rawCategory, rawDetails] = String(value).split(/:\s*(.+)/);
    const matchedCategory = SKILL_CATEGORIES.find(
      (category) => category.toLowerCase() === String(rawCategory || "").trim().toLowerCase(),
    );
    if (matchedCategory && rawDetails) {
      categories[matchedCategory].push(...splitSkillText(rawDetails));
    } else {
      uncategorized.push(...splitSkillText(value));
    }
  }

  for (const skill of uncategorized) {
    categories["Business and Soft Skills"].push(skill);
  }

  return Object.fromEntries(
    Object.entries(categories).map(([category, values]) => [
      category,
      values.filter(
        (skill, index, list) => list.findIndex((candidate) => candidate.toLowerCase() === skill.toLowerCase()) === index,
      ),
    ]),
  );
}

export function categoriesToSkills(categories) {
  return Object.entries(categories)
    .map(([category, values]) => {
      const skills = (Array.isArray(values) ? values : []).map(normalizeSkillName).filter(Boolean);
      return skills.length ? { skill_name: `${category}: ${skills.join(", ")}` } : null;
    })
    .filter(Boolean);
}
