/**
 * Starting skills for common target roles, offered when the learner changes
 * their role. Any other role asks the orchestrator for suggestions instead.
 */
const ROLE_SKILLS: Record<string, string[]> = {
  "software developer": ["python", "java", "data structures", "algorithms", "git", "sql", "oops"],
  "full stack developer": ["javascript", "react", "node.js", "html", "css", "sql", "rest api", "git"],
  "frontend developer": ["html", "css", "javascript", "typescript", "react", "responsive design", "git"],
  "backend developer": ["python", "java", "node.js", "sql", "rest api", "docker", "git"],
  "data analyst": ["sql", "excel", "python", "pandas", "power bi", "tableau", "statistics"],
  "data scientist": ["python", "pandas", "numpy", "statistics", "machine learning", "scikit-learn", "sql", "data visualization"],
  "machine learning engineer": ["python", "machine learning", "deep learning", "pytorch", "tensorflow", "mlops", "sql"],
  "ai engineer": ["python", "llm", "langchain", "langgraph", "rag", "prompt engineering", "vector databases"],
  "devops engineer": ["linux", "docker", "kubernetes", "ci/cd", "aws", "terraform", "git"],
  "cloud engineer": ["aws", "azure", "linux", "networking", "docker", "terraform"],
  "qa / test engineer": ["manual testing", "selenium", "test cases", "api testing", "sql", "jira"],
  "business analyst": ["requirements gathering", "excel", "sql", "power bi", "communication", "documentation"],
  "ui/ux designer": ["figma", "wireframing", "prototyping", "user research", "design systems"],
  "cybersecurity analyst": ["networking", "linux", "security fundamentals", "siem", "vulnerability assessment"],
  "product manager": ["product strategy", "roadmapping", "user research", "analytics", "communication"],
};

/** The known starting skills for this role, or null when it is not a common one. */
export function knownRoleSkills(role: string): string[] | null {
  return ROLE_SKILLS[role.toLowerCase().trim().replace(/\s+/g, " ")] ?? null;
}
