import { gatewayInvokeUrl, invokeAgent } from "./gatewayClient";

const INVOKE_URL = gatewayInvokeUrl(import.meta.env.VITE_CODEFORGE_AGENT_NAME, "codeforge_agent");

function invoke<T>(action: string, payload: Record<string, unknown> = {}): Promise<T> {
  return invokeAgent<T>(INVOKE_URL, action, payload);
}

export async function checkCodeForgeHealth(): Promise<boolean> {
  try {
    const result = await invoke<{ status: string }>("health");
    return result.status === "ok";
  } catch {
    return false;
  }
}

export interface Student {
  id: number;
  display_name: string;
  email: string;
  bio: string | null;
  timezone: string;
  is_active: boolean;
}

export interface EnsureSessionResult {
  student: Student;
  sessionToken: string;
  expiresAt: string;
}

export function ensureSession(name: string, email: string) {
  return invoke<EnsureSessionResult>("ensure_session", { name, email });
}

export interface Course {
  id: number;
  name: string;
  slug: string;
  description: string;
  icon: string;
  technology_count: number;
}

export function listCourses(sessionToken: string) {
  return invoke<{ courses: Course[] }>("list_courses", { sessionToken });
}

export interface Technology {
  id: number;
  name: string;
  slug: string;
  description: string;
  icon: string;
  topic_count: number;
}

export function listTechnologies(sessionToken: string, course_slug: string) {
  return invoke<{ course: Course; technologies: Technology[] }>("list_technologies", { sessionToken, course_slug });
}

export interface Topic {
  id: number;
  name: string;
  slug: string;
  description: string;
  problem_count: number;
  progress: string;
  sequence: number;
}

export function listTopics(sessionToken: string, course_slug: string, technology_slug: string) {
  return invoke<{ course: Course; technology: Technology; topics: Topic[] }>("list_topics", {
    sessionToken,
    course_slug,
    technology_slug,
  });
}

export interface ProblemSummary {
  id: number;
  name: string;
  slug: string;
  description: string;
  difficulty: "Easy" | "Medium" | "Hard";
  language: string;
  question_type: "code" | "mcq";
  max_score: number;
  progress: string;
  best_score: number;
  attempts: number;
  sequence: number;
}

export function listProblems(sessionToken: string, course_slug: string, technology_slug: string, topic_slug: string) {
  return invoke<{ course: Course; technology: Technology; topic: Topic; problems: ProblemSummary[] }>("list_problems", {
    sessionToken,
    course_slug,
    technology_slug,
    topic_slug,
  });
}

export interface ProblemExample {
  input: string;
  output: string;
}

export interface PublicTest {
  id: number;
  input: string;
  expectedOutput: string;
  sequence: number;
}

export interface ProblemDetail extends ProblemSummary {
  // Present only when question_type is "code"; absent for "mcq" (see options below).
  input_format?: string;
  output_format?: string;
  constraints?: string;
  examples?: ProblemExample[];
  starter_code?: string;
  judge0_language_id?: number;
  public_tests?: PublicTest[];
  // Present only when question_type is "mcq" -- option key -> option text.
  // Never includes the correct key or an explanation; those only come back
  // from submitMcqAnswer, after the student has actually answered.
  options?: Record<string, string>;
}

export function getProblem(
  sessionToken: string,
  course_slug: string,
  technology_slug: string,
  topic_slug: string,
  problem_slug: string,
) {
  return invoke<{ course: Course; technology: Technology; topic: Topic; problem: ProblemDetail }>("get_problem", {
    sessionToken,
    course_slug,
    technology_slug,
    topic_slug,
    problem_slug,
  });
}

export interface EvaluationTest {
  sequence: number;
  label: string;
  hidden: boolean;
  passed: boolean;
  status: string;
  input: string | null;
  expectedOutput: string | null;
  actualOutput: string | null;
  stderr: string | null;
  compileOutput: string | null;
  message: string | null;
  time: number | null;
  memory: number | null;
}

export interface EvaluationResult {
  submissionId: number;
  mode: "run" | "submit";
  status: string;
  score: number;
  passedTests: number;
  totalTests: number;
  tests: EvaluationTest[];
}

export function runProblem(sessionToken: string, problem_id: number, sourceCode: string) {
  return invoke<EvaluationResult>("run_problem", { sessionToken, problem_id, sourceCode });
}

export function submitProblem(sessionToken: string, problem_id: number, sourceCode: string) {
  return invoke<EvaluationResult>("submit_problem", { sessionToken, problem_id, sourceCode });
}

export interface McqAnswerResult {
  submissionId: number;
  mode: "submit";
  status: string;
  score: number;
  isCorrect: boolean;
  correctKey: string;
  explanation: string;
}

export function submitMcqAnswer(sessionToken: string, problem_id: number, selectedKey: string) {
  return invoke<McqAnswerResult>("submit_mcq_answer", { sessionToken, problem_id, selectedKey });
}

export interface TutorGuidance {
  source: "ai" | "guided";
  errorCategory: string;
  explanation: string;
  workflow: string[];
  nextAction: string;
  fullSolutionAllowed: false;
}

export function askTutor(sessionToken: string, problem_id: number, submissionId: number, hintLevel = 2) {
  return invoke<{ guidance: TutorGuidance }>("tutor", { sessionToken, problem_id, submissionId, hintLevel });
}

export function getDashboard(sessionToken: string) {
  return invoke<Record<string, any>>("dashboard", { sessionToken });
}

export interface Judge0Language {
  id: number;
  name: string;
}

export function listLanguages() {
  return invoke<{ languages: Judge0Language[] }>("list_languages");
}

export interface PlaygroundResult {
  status: { id: number; description: string };
  stdout: string | null;
  stderr: string | null;
  compile_output: string | null;
  message: string | null;
  time: string | null;
  memory: number | null;
}

export function runPlayground(languageId: number, sourceCode: string, stdin = "") {
  return invoke<PlaygroundResult>("run_playground", { languageId, sourceCode, stdin });
}
