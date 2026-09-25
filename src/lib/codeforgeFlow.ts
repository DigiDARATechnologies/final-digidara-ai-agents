import type { ChatOption, User } from "../types";
import {
  askTutor,
  ensureSession,
  listCourses,
  listProblems,
  listTechnologies,
  listTopics,
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

function courseOptions(courses: Course[]): ChatOption[] {
  return [
    ...courses.map((c) => ({ label: c.name, value: c.slug, description: c.description })),
    { label: "Code Playground", value: "__playground__", description: "Write and run any code freely, not tied to a course." },
  ];
}

function technologyOptions(technologies: Technology[]): ChatOption[] {
  return technologies.map((t) => ({ label: t.name, value: t.slug, description: `${t.topic_count} topics` }));
}

function topicOptions(topics: Topic[]): ChatOption[] {
  return topics.map((t) => ({ label: t.name, value: t.slug, description: `${t.problem_count} problems · ${t.progress}` }));
}

function problemOptions(problems: ProblemSummary[]): ChatOption[] {
  return problems.map((p) => ({
    label: `${p.name} (${p.difficulty})`,
    value: p.slug,
    description: p.attempts > 0 ? `${p.progress} · best ${p.best_score}` : p.progress,
  }));
}

// Same pattern as Aptitude's option map: {A: "text", B: "text", ...} -> clickable buttons.
function mcqOptions(options: Record<string, string>): ChatOption[] {
  return Object.entries(options).map(([value, label]) => ({ value, label: `${value}. ${label}` }));
}

async function enterTopics(state: CodeForgeFlowState): Promise<{ state: CodeForgeFlowState; messages: CodeForgeFlowMessage[] }> {
  const { topics } = await listTopics(state.sessionToken!, state.courseSlug!, state.technologySlug!);
  return {
    state: { ...state, step: "awaiting_topic", topics },
    messages: [{ text: `${state.technologyName} topics:`, options: topicOptions(topics) }],
  };
}

async function enterProblems(state: CodeForgeFlowState): Promise<{ state: CodeForgeFlowState; messages: CodeForgeFlowMessage[] }> {
  const { problems } = await listProblems(state.sessionToken!, state.courseSlug!, state.technologySlug!, state.topicSlug!);
  return {
    state: { ...state, step: "awaiting_problem", problems },
    messages: [{ text: `${state.topicName} problems:`, options: problemOptions(problems) }],
  };
}

async function enterCourses(state: CodeForgeFlowState): Promise<{ state: CodeForgeFlowState; messages: CodeForgeFlowMessage[] }> {
  const { courses } = await listCourses(state.sessionToken!);
  return {
    state: { ...state, step: "awaiting_course", courses },
    messages: [{ text: "Choose a course to practice:", options: courseOptions(courses) }],
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
        text: `Hi ${student.display_name.split(" ")[0]}! Choose a course to practice:`,
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
          { label: "Choose another problem", value: "choose_another_problem" },
          { label: "Back to topics", value: "back_to_topics" },
          { label: "Back to courses", value: "back_to_courses" },
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

  // Cross-cutting navigation commands, reachable from any step.
  if (command === "back_to_courses") return enterCourses(state);
  if (command === "back_to_topics") return enterTopics(state);
  if (command === "choose_another_problem") return enterProblems(state);

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
        return await enterTopics(next);
      } catch (error) {
        return { state, messages: [{ text: `Could not load topics: ${(error as Error).message}`, options: technologyOptions(state.technologies) }] };
      }
    }

    case "awaiting_topic": {
      const topic = matchSlugOrName(state.topics, trimmed);
      if (!topic) return { state, messages: [{ text: "Pick a topic from the list.", options: topicOptions(state.topics) }] };
      const next = { ...state, topicSlug: topic.slug, topicName: topic.name };
      try {
        return await enterProblems(next);
      } catch (error) {
        return { state, messages: [{ text: `Could not load problems: ${(error as Error).message}`, options: topicOptions(state.topics) }] };
      }
    }

    case "awaiting_problem": {
      const problem = matchSlugOrName(state.problems, trimmed);
      if (!problem) return { state, messages: [{ text: "Pick a problem from the list.", options: problemOptions(state.problems) }] };
      try {
        const { problem: detail } = await getProblem(
          state.sessionToken!,
          state.courseSlug!,
          state.technologySlug!,
          state.topicSlug!,
          problem.slug,
        );
        if (detail.question_type === "mcq") {
          const options = detail.options ?? {};
          return {
            state: {
              ...state,
              step: "awaiting_mcq_answer",
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
            options: [
              { label: "Choose another problem", value: "choose_another_problem" },
              { label: "Back to topics", value: "back_to_topics" },
              { label: "Back to courses", value: "back_to_courses" },
            ],
          }],
        };
      } catch (error) {
        return { state, messages: [{ text: `Could not submit your answer: ${(error as Error).message}`, options: mcqOptions(options) }] };
      }
    }
  }
}
