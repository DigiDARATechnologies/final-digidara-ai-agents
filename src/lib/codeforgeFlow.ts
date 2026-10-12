import type { ChatOption, User } from "../types";
import { easyMediumHard, goalLine, goalMatchScore, learnerGoal, learnerLevel } from "./learnerContext";
import {
  askTutor,
  ensureSession,
  listCourses,
  listLevelProblems,
  listTechnologies,
  getProblem,
  runProblem,
  submitProblem,
  submitMcqAnswer,
  type Course,
  type EvaluationResult,
  type ProblemSummary,
  type Technology,
  type TutorGuidance,
  type Topic,
} from "./codeforgeApi";

export type CodeForgeStep =
  | "awaiting_course"
  | "awaiting_technology"
  | "awaiting_topic"
  | "awaiting_problem"
  | "awaiting_code"
  | "awaiting_mcq_answer";

export interface CodeForgeFlowMessage {
  text: string;
  options?: ChatOption[];
}

export interface CodeForgeFlowState {
  step: CodeForgeStep;
  sessionToken?: string;
  studentName?: string;
  courses: Course[];
  technologies: Technology[];
  topics: Topic[];
  problems: ProblemSummary[];
  courseSlug?: string;
  courseName?: string;
  technologySlug?: string;
  technologyName?: string;
  topicSlug?: string;
  topicName?: string;
  problemSlug?: string;
  problemId?: number;
  problemName?: string;
  starterCode?: string;
  mcqOptions?: Record<string, string>;
  lastResult?: EvaluationResult;
  lastGuidance?: TutorGuidance;
}

function matchSlugOrName<T extends { slug: string; name: string }>(list: T[], value: string): T | undefined {
  const needle = value.trim().toLowerCase();
  return list.find((item) => item.slug === needle || item.name.toLowerCase() === needle);
}

/** Courses ordered by how well they fit the learner's goal; the best fit first. */
function rankCourses(courses: Course[]): { ordered: Course[]; recommended: Course | null } {
  const goal = learnerGoal();
  if (!goal) return { ordered: courses, recommended: null };
  const scored = courses.map((course, index) => ({ course, index, score: goalMatchScore(goal, course.name, course.description) }));
  scored.sort((a, b) => b.score - a.score || a.index - b.index);
  return { ordered: scored.map((s) => s.course), recommended: scored[0]?.score > 0 ? scored[0].course : null };
}

/** "Hi Asha! For your goal (Data Analyst · SQL, Excel), I recommend Data Analytics." */
function courseGreeting(courses: Course[], firstName?: string): string {
  const goal = learnerGoal();
  const { recommended } = rankCourses(courses);
  const hello = firstName ? `Hi ${firstName}! ` : "";
  if (goal && recommended) return `${hello}For your goal (${goalLine(goal)}), I recommend **${recommended.name}**. Choose a course to practice:`;
  return `${hello}Choose a course to practice:`;
}

function courseOptions(courses: Course[]): ChatOption[] {
  const { ordered, recommended } = rankCourses(courses);
  return [
    { label: "📋 Problem list", value: "__problemset__", description: "Every problem in every language, LeetCode style. Your level's problems are open." },
    ...ordered.map((c) => ({
      label: c === recommended ? `⭐ ${c.name} · recommended for you` : c.name,
      value: c.slug,
      description: c.description,
    })),
    { label: "Code Playground", value: "__playground__", description: "Write and run any code freely, not tied to a course." },
  ];
}

const LEVEL_LABELS = { beginner: "Beginner", medium: "Medium", hard: "Hard", professional: "Professional" } as const;

/** "Beginner" and its problem difficulty, "Easy". */
function levelNames(): { level: string; difficulty: string } {
  const level = learnerLevel("codeforge_agent");
  const difficulty = easyMediumHard("codeforge_agent");
  return { level: LEVEL_LABELS[level], difficulty: difficulty.charAt(0).toUpperCase() + difficulty.slice(1) };
}

function technologyOptions(technologies: Technology[]): ChatOption[] {
  const { level, difficulty } = levelNames();
  return technologies.map((t) => ({ label: t.name, value: t.slug, description: `${level} level: ${difficulty} problems` }));
}

function problemOptions(problems: ProblemSummary[]): ChatOption[] {
  return problems.map((p) => ({
    label: `${p.progress === "Solved" ? "✓ " : ""}${p.name}`,
    value: p.slug,
    description: [p.topic_name, p.attempts > 0 ? `${p.progress} · best ${p.best_score}` : p.progress].filter(Boolean).join(" · "),
  }));
}

/** The first unsolved problem after the current one (then from the start). */
function nextProblem(state: CodeForgeFlowState): ProblemSummary | undefined {
  const index = state.problems.findIndex((p) => p.slug === state.problemSlug);
  const ordered = [...state.problems.slice(index + 1), ...state.problems.slice(0, Math.max(0, index))];
  return ordered.find((p) => p.progress !== "Solved");
}

/** Ways to move on after a problem. */
function afterProblemOptions(state: CodeForgeFlowState): ChatOption[] {
  const { level } = levelNames();
  const next = nextProblem(state);
  return [
    ...(next ? [{ label: `Next problem: ${next.name}`, value: next.slug }] : []),
    { label: `All ${level} problems`, value: "choose_another_problem" },
    { label: "📋 Problem list", value: "__problemset__" },
    { label: "Other technology", value: "back_to_technologies" },
    { label: "Back to courses", value: "back_to_courses" },
  ];
}

// Same pattern as Aptitude's option map: {A: "text", B: "text", ...} -> clickable buttons.
function mcqOptions(options: Record<string, string>): ChatOption[] {
  return Object.entries(options).map(([value, label]) => ({ value, label: `${value}. ${label}` }));
}

/** Every problem at the learner's level in the chosen technology -- no topic
 * step: practice is by level. The server only serves this level's problems. */
async function enterLevelProblems(state: CodeForgeFlowState): Promise<{ state: CodeForgeFlowState; messages: CodeForgeFlowMessage[] }> {
  const { level, difficulty } = levelNames();
  const { problems } = await listLevelProblems(state.sessionToken!, state.courseSlug!, state.technologySlug!, difficulty.toLowerCase());
  const next: CodeForgeFlowState = { ...state, step: "awaiting_problem", problems, topics: [] };
  const solved = problems.filter((p) => p.progress === "Solved").length;
  const navigation: ChatOption[] = [
    { label: "Other technology", value: "back_to_technologies" },
    { label: "Back to courses", value: "back_to_courses" },
  ];
  if (!problems.length) {
    return {
      state: next,
      messages: [{ text: `${state.technologyName} has no ${difficulty} problems yet for your ${level} level. Try another technology.`, options: navigation }],
    };
  }
  const heading = solved === problems.length
    ? `🎉 You've solved every ${level} (${difficulty}) problem in ${state.technologyName}. Your level moves up automatically at 100% — check Job Readiness. You can redo any of them:`
    : `${state.technologyName} · ${level} level: ${problems.length} ${difficulty} problems, ${solved} solved. Solve all of them to unlock the next level.`;
  return { state: next, messages: [{ text: heading, options: [...problemOptions(problems), ...navigation] }] };
}

async function enterTechnologies(state: CodeForgeFlowState): Promise<{ state: CodeForgeFlowState; messages: CodeForgeFlowMessage[] }> {
  if (!state.courseSlug) return enterCourses(state);
  const { technologies } = await listTechnologies(state.sessionToken!, state.courseSlug);
  return {
    state: { ...state, step: "awaiting_technology", technologies },
    messages: [{ text: `${state.courseName ?? "Course"} technologies:`, options: technologyOptions(technologies) }],
  };
}

async function enterCourses(state: CodeForgeFlowState): Promise<{ state: CodeForgeFlowState; messages: CodeForgeFlowMessage[] }> {
  const { courses } = await listCourses(state.sessionToken!);
  return {
    state: { ...state, step: "awaiting_course", courses },
    messages: [{ text: courseGreeting(courses), options: courseOptions(courses) }],
  };
}

export async function openCodeForgeChat(
  user: User,
): Promise<{ state: CodeForgeFlowState; messages: CodeForgeFlowMessage[] }> {
  const base: CodeForgeFlowState = { step: "awaiting_course", courses: [], technologies: [], topics: [], problems: [] };
  try {
    const { sessionToken, student } = await ensureSession(user.name, user.email);
    const { courses } = await listCourses(sessionToken);
    return {
      state: { ...base, sessionToken, studentName: student.display_name, courses },
      messages: [{
        text: courseGreeting(courses, student.display_name.split(" ")[0]),
        options: courseOptions(courses),
      }],
    };
  } catch (error) {
    return {
      state: base,
      messages: [{ text: `I could not connect to CodeForge: ${(error as Error).message}`, options: [{ label: "Try again", value: "retry" }] }],
    };
  }
}

function formatResult(result: EvaluationResult): string {
  const lines: string[] = [
    result.mode === "submit"
      ? `${result.status} — ${result.passedTests}/${result.totalTests} tests passed · Score ${result.score}/100`
      : `${result.status} — ${result.passedTests}/${result.totalTests} public tests passed`,
  ];
  for (const test of result.tests) {
    lines.push(`\n${test.passed ? "✅" : "❌"} ${test.label}: ${test.status}`);
    if (!test.passed && !test.hidden) {
      if (test.input) lines.push(`  Input: ${test.input.trim()}`);
      if (test.expectedOutput) lines.push(`  Expected: ${test.expectedOutput.trim()}`);
      if (test.actualOutput) lines.push(`  Received: ${test.actualOutput.trim()}`);
      else if (test.stderr) lines.push(`  Error: ${test.stderr.trim()}`);
      else if (test.compileOutput) lines.push(`  Compile error: ${test.compileOutput.trim()}`);
    }
  }
  return lines.join("\n");
}

function formatGuidance(guidance: TutorGuidance): string {
  const lines = [
    `${guidance.source === "ai" ? "✦ AI Tutor" : "✦ Guided fallback"} — ${guidance.errorCategory}`,
    "",
    guidance.explanation,
    "",
    "Workflow:",
    ...guidance.workflow.map((step, i) => `${i + 1}. ${step}`),
    "",
    `Next: ${guidance.nextAction}`,
  ];
  return lines.join("\n");
}

export async function runCodeForgeCode(
  state: CodeForgeFlowState,
  code: string,
): Promise<{ state: CodeForgeFlowState; messages: CodeForgeFlowMessage[] }> {
  if (!state.sessionToken || !state.problemId) return { state, messages: [] };
  try {
    const result = await runProblem(state.sessionToken, state.problemId, code);
    const failed = result.status !== "Accepted";
    return {
      state: { ...state, lastResult: result, lastGuidance: undefined },
      messages: [{ text: formatResult(result), options: failed ? [{ label: "Explain this error", value: "explain_error" }] : undefined }],
    };
  } catch (error) {
    return { state, messages: [{ text: `Could not run your code: ${(error as Error).message}` }] };
  }
}

export async function submitCodeForgeCode(
  state: CodeForgeFlowState,
  code: string,
): Promise<{ state: CodeForgeFlowState; messages: CodeForgeFlowMessage[] }> {
  if (!state.sessionToken || !state.problemId) return { state, messages: [] };
  try {
    const result = await submitProblem(state.sessionToken, state.problemId, code);
    const accepted = result.status === "Accepted";
    const nextOptions: ChatOption[] = accepted
      ? [
          ...afterProblemOptions({ ...state, problems: state.problems.map((p) => (p.slug === state.problemSlug ? { ...p, progress: "Solved" } : p)) }),
        ]
      : [{ label: "Explain this error", value: "explain_error" }];
    return {
      state: { ...state, step: accepted ? "awaiting_problem" : "awaiting_code", lastResult: result, lastGuidance: undefined },
      messages: [{ text: formatResult(result), options: nextOptions }],
    };
  } catch (error) {
    return { state, messages: [{ text: `Could not submit your code: ${(error as Error).message}` }] };
  }
}

export async function handleCodeForgeText(
  state: CodeForgeFlowState,
  text: string,
): Promise<{ state: CodeForgeFlowState; messages: CodeForgeFlowMessage[] }> {
  const trimmed = text.trim();
  const command = trimmed.toLowerCase();

  // Cross-cutting navigation commands, reachable from any step. Buttons from
  // chats saved before practice was by level ("Back to topics", "Next
  // topic") now open the level's problem list.
  if (command === "back_to_courses") return enterCourses(state);
  if (command === "back_to_technologies") return enterTechnologies(state);
  if ((command === "choose_another_problem" || command === "back_to_topics" || command === "next_topic") && state.technologySlug) {
    return enterLevelProblems(state);
  }
  // A problem picked from "Next problem" while a chat is at another step.
  if (state.step !== "awaiting_problem" && state.problems.some((p) => p.slug === command)) {
    return handleCodeForgeText({ ...state, step: "awaiting_problem" }, trimmed);
  }

  switch (state.step) {
    case "awaiting_course": {
      const course = matchSlugOrName(state.courses, trimmed);
      if (!course) return { state, messages: [{ text: "Pick a course from the list.", options: courseOptions(state.courses) }] };
      try {
        const { technologies } = await listTechnologies(state.sessionToken!, course.slug);
        return {
          state: { ...state, step: "awaiting_technology", courseSlug: course.slug, courseName: course.name, technologies },
          messages: [{ text: `${course.name} technologies:`, options: technologyOptions(technologies) }],
        };
      } catch (error) {
        return { state, messages: [{ text: `Could not load technologies: ${(error as Error).message}`, options: courseOptions(state.courses) }] };
      }
    }

    case "awaiting_technology": {
      const technology = matchSlugOrName(state.technologies, trimmed);
      if (!technology) return { state, messages: [{ text: "Pick a technology from the list.", options: technologyOptions(state.technologies) }] };
      const next = { ...state, technologySlug: technology.slug, technologyName: technology.name };
      try {
        return await enterLevelProblems(next);
      } catch (error) {
        return { state, messages: [{ text: `Could not load problems: ${(error as Error).message}`, options: technologyOptions(state.technologies) }] };
      }
    }

    case "awaiting_topic": {
      // A chat saved at the old topic step: practice is by level now.
      try {
        return await enterLevelProblems(state);
      } catch (error) {
        return { state, messages: [{ text: `Could not load problems: ${(error as Error).message}`, options: technologyOptions(state.technologies) }] };
      }
    }

    case "awaiting_problem": {
      const problem = matchSlugOrName(state.problems, trimmed);
      if (!problem) return { state, messages: [{ text: "Pick a problem from the list.", options: [...problemOptions(state.problems), ...afterProblemOptions(state).slice(1)] }] };
      const topicSlug = problem.topic_slug ?? state.topicSlug!;
      try {
        const { problem: detail } = await getProblem(
          state.sessionToken!,
          state.courseSlug!,
          state.technologySlug!,
          topicSlug,
          problem.slug,
        );
        if (detail.question_type === "mcq") {
          const options = detail.options ?? {};
          return {
            state: {
              ...state,
              step: "awaiting_mcq_answer",
              topicSlug,
              topicName: problem.topic_name ?? state.topicName,
              problemSlug: detail.slug,
              problemId: detail.id,
              problemName: detail.name,
              mcqOptions: options,
              lastResult: undefined,
              lastGuidance: undefined,
            },
            messages: [{
              text: `${detail.name} (${detail.difficulty})\n\n${detail.description}`,
              options: mcqOptions(options),
            }],
          };
        }
        const exampleText = (detail.examples ?? [])
          .map((ex, i) => `Example ${i + 1}:\n  Input: ${ex.input || "(none)"}\n  Output: ${ex.output}`)
          .join("\n");
        return {
          state: {
            ...state,
            step: "awaiting_code",
            topicSlug,
            topicName: problem.topic_name ?? state.topicName,
            problemSlug: detail.slug,
            problemId: detail.id,
            problemName: detail.name,
            starterCode: detail.starter_code,
            lastResult: undefined,
            lastGuidance: undefined,
          },
          messages: [{
            text: `${detail.name} (${detail.difficulty})\n\n${detail.description}\n\nInput: ${detail.input_format}\nOutput: ${detail.output_format}\nConstraints: ${detail.constraints}\n\n${exampleText}\n\nWrite your ${detail.language} solution below, then Run or Submit.`,
          }],
        };
      } catch (error) {
        return { state, messages: [{ text: `Could not load that problem: ${(error as Error).message}`, options: problemOptions(state.problems) }] };
      }
    }

    case "awaiting_code": {
      if (command === "explain_error") {
        if (!state.sessionToken || !state.problemId || !state.lastResult) {
          return { state, messages: [{ text: "Run or submit your code first, then I can explain any error." }] };
        }
        try {
          const { guidance } = await askTutor(state.sessionToken, state.problemId, state.lastResult.submissionId, 2);
          return { state: { ...state, lastGuidance: guidance }, messages: [{ text: formatGuidance(guidance) }] };
        } catch (error) {
          return { state, messages: [{ text: `Could not reach the tutor: ${(error as Error).message}` }] };
        }
      }
      return {
        state,
        messages: [{ text: 'Use the Run or Submit buttons to try your code, or click "Explain this error" after a failed attempt.' }],
      };
    }

    case "awaiting_mcq_answer": {
      const options = state.mcqOptions ?? {};
      // Accepts a bare key ("B"), "option B", or "B." -- matches the values
      // the option buttons send, and forgives a learner typing one by hand.
      const match = /^(?:option\s*)?([a-z0-9]+)\.?$/i.exec(trimmed);
      const selectedKey = match ? Object.keys(options).find((key) => key.toLowerCase() === match[1].toLowerCase()) : undefined;
      if (!selectedKey || !state.sessionToken || !state.problemId) {
        return { state, messages: [{ text: "Pick an option from the list.", options: mcqOptions(options) }] };
      }
      try {
        const result = await submitMcqAnswer(state.sessionToken, state.problemId, selectedKey);
        const feedback = [
          result.isCorrect ? "Correct!" : "Not quite.",
          !result.isCorrect ? `Correct answer: ${result.correctKey}. ${options[result.correctKey] ?? ""}` : "",
          result.explanation,
        ].filter(Boolean).join("\n\n");
        return {
          state: { ...state, step: "awaiting_problem" },
          messages: [{
            text: feedback,
            options: afterProblemOptions(result.isCorrect
              ? { ...state, problems: state.problems.map((p) => (p.slug === state.problemSlug ? { ...p, progress: "Solved" } : p)) }
              : state),
          }],
        };
      } catch (error) {
        return { state, messages: [{ text: `Could not submit your answer: ${(error as Error).message}`, options: mcqOptions(options) }] };
      }
    }
  }
}

/** Opens a problem picked in the problem list, in this chat. */
export async function openCodeForgeProblem(
  state: CodeForgeFlowState,
  target: { courseSlug: string; technologySlug: string; technologyName: string; problem: ProblemSummary },
): Promise<{ state: CodeForgeFlowState; messages: CodeForgeFlowMessage[] }> {
  const next: CodeForgeFlowState = {
    ...state,
    step: "awaiting_problem",
    courseSlug: target.courseSlug,
    technologySlug: target.technologySlug,
    technologyName: target.technologyName,
    problems: state.technologySlug === target.technologySlug && state.problems.some((p) => p.slug === target.problem.slug)
      ? state.problems
      : [target.problem],
  };
  return handleCodeForgeText(next, target.problem.slug);
}
