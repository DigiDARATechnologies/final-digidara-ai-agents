/**
 * The learner's goal and levels for the agents' own chat flows.
 *
 * Every agent opens its chat in the browser (choose a course, pick a topic,
 * pick a role...). Those openings read this instead of asking again for what
 * onboarding already collected: the target role, skills, degree, experience
 * and the learner's level with each agent. App.tsx keeps it current.
 */
import type { LearnerSummary, LevelId } from "./learnerApi";

let summary: LearnerSummary | null = null;

export function setLearnerContext(next: LearnerSummary | null): void {
  summary = next;
}

export interface LearnerGoal {
  targetRole: string;
  degree: string;
  skills: string[];
  experience: "fresher" | "experienced";
}

/** The learner's goal, or null before onboarding (flows then ask as before). */
export function learnerGoal(): LearnerGoal | null {
  const profile = summary?.profile;
  if (!profile?.onboarding_completed || !profile.target_role.trim()) return null;
  return {
    targetRole: profile.target_role.trim(),
    degree: profile.degree.trim(),
    skills: profile.skills,
    experience: profile.experience,
  };
}

export function learnerLevel(agentName: string): LevelId {
  return summary?.levels.find((level) => level.agent_name === agentName)?.level ?? "beginner";
}

/** "Easy" / "Medium" / "Hard" words, for agents that use them. */
export function easyMediumHard(agentName: string): "easy" | "medium" | "hard" {
  const level = learnerLevel(agentName);
  return level === "beginner" ? "easy" : level === "medium" ? "medium" : "hard";
}

/** "beginner" / "intermediate" / "advanced", for agents that use those. */
export function beginnerToAdvanced(agentName: string): "beginner" | "intermediate" | "advanced" {
  const level = learnerLevel(agentName);
  return level === "beginner" ? "beginner" : level === "medium" ? "intermediate" : "advanced";
}

/** Title-cased role for display: "ai engineer" -> "AI Engineer". */
export function displayRole(role: string): string {
  const upper = new Set(["ai", "ml", "ui", "ux", "qa", "sql", "api", "it", "hr", "llm", "nlp", "devops", "bi"]);
  return role
    .split(/\s+/)
    .map((word) => (upper.has(word.toLowerCase()) ? word.toUpperCase() : word.charAt(0).toUpperCase() + word.slice(1)))
    .join(" ")
    .replace(/Devops/i, "DevOps");
}

/** "AI Engineer · python, llm, langgraph" for one-line mentions. */
export function goalLine(goal: LearnerGoal, maxSkills = 4): string {
  const skills = goal.skills.slice(0, maxSkills).join(", ");
  return skills ? `${displayRole(goal.targetRole)} · ${skills}` : displayRole(goal.targetRole);
}

// Words that link a role or skill to a course or topic name.
const AREA_KEYWORDS: Record<string, string[]> = {
  "generative ai": ["llm", "gpt", "genai", "generative", "langchain", "langgraph", "rag", "agent", "agentic", "aiagent", "prompt", "openai", "qdrant", "vector", "ai engineer"],
  "machine learning": ["machine learning", "ml", "ai", "deep learning", "tensorflow", "pytorch", "scikit", "sklearn", "ai engineer", "data scientist"],
  "data science": ["data scien", "pandas", "numpy", "statistics", "ml", "machine learning"],
  "data analytics": ["data analy", "excel", "power bi", "tableau", "sql", "analyst", "bi", "dashboard"],
  "full stack": ["full stack", "fullstack", "django", "flask", "react", "javascript", "html", "css", "node", "web", "frontend", "backend", "developer"],
  python: ["python"],
  sql: ["sql", "mysql", "database"],
  javascript: ["javascript", "js", "react", "node", "frontend"],
};

/** How well one course/topic name and description matches the learner's goal. */
export function goalMatchScore(goal: LearnerGoal, name: string, description = ""): number {
  const haystack = `${name} ${description}`.toLowerCase();
  const wants = [goal.targetRole, ...goal.skills].map((s) => s.toLowerCase().trim()).filter((s) => s.length >= 2);
  let score = 0;
  for (const [area, words] of Object.entries(AREA_KEYWORDS)) {
    if (!haystack.includes(area)) continue;
    for (const want of wants) {
      const linked = words.some((word) => want.includes(word) || (want.length >= 3 && word.includes(want)));
      if (linked) score += want === goal.targetRole.toLowerCase().trim() ? 3 : 1;
    }
  }
  for (const want of wants) if (want.length > 2 && haystack.includes(want)) score += 2;
  return score;
}
