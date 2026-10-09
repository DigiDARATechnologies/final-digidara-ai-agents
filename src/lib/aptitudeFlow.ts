import type { ChatOption, User } from "../types";
import { beginnerToAdvanced, displayRole, learnerGoal } from "./learnerContext";
import { abandonAptitudeTest, createAptitudeTest, ensureAptitudeSession, getAptitudeQuestion, getMixedTestConfig, saveMixedTestConfig, getAptitudeResults, requestAptitudeHint, submitAptitudeAnswer, skipAptitudeQuestion, downloadAptitudeReport, type AptitudeQuestion } from "./aptitudeApi";

export type AptitudeStep = "awaiting_mode" | "awaiting_category" | "awaiting_level" | "awaiting_language" | "awaiting_question" | "awaiting_next_question" | "completed";
export interface AptitudeFlowState { step: AptitudeStep; mode?: "mixed" | "category_practice"; category?: string; level?: "Beginner" | "Intermediate" | "Advanced"; technicalLanguage?: "C" | "Java" | "Python" | "SQL"; sessionToken?: string; testId?: string; question?: AptitudeQuestion; score?: number; totalQuestions?: number; hintsRemaining?: number; hintText?: string; tokenInterrupted?: boolean; }
export interface AptitudeFlowMessage { text: string; options?: ChatOption[]; }
const categories = ["Quantitative Aptitude", "Logical Reasoning", "Verbal Ability", "Analytical Reasoning", "Computer Fundamentals", "Technical Aptitude"];
const categoryOptions = categories.map((value) => ({ label: value, value }));
const levelOptions = ["Beginner", "Intermediate", "Advanced"].map((value) => ({ label: value, value }));
const languageOptions = ["Python", "Java", "C", "SQL"].map((value) => ({ label: value, value }));

type RoleFamily = "engineering" | "data" | "business";

/** Which aptitude categories a role is usually tested on, most important first,
 * and a 20-question mix weighted the same way. */
const ROLE_FAMILIES: Record<RoleFamily, { focus: string; mix: Record<string, number> }> = {
  engineering: { focus: "Technical Aptitude", mix: {
    "Technical Aptitude": 6, "Computer Fundamentals": 4, "Logical Reasoning": 4, "Quantitative Aptitude": 3, "Analytical Reasoning": 2, "Verbal Ability": 1 } },
  data: { focus: "Quantitative Aptitude", mix: {
    "Quantitative Aptitude": 6, "Analytical Reasoning": 5, "Logical Reasoning": 4, "Technical Aptitude": 3, "Computer Fundamentals": 1, "Verbal Ability": 1 } },
  business: { focus: "Verbal Ability", mix: {
    "Verbal Ability": 6, "Logical Reasoning": 4, "Quantitative Aptitude": 4, "Analytical Reasoning": 4, "Computer Fundamentals": 1, "Technical Aptitude": 1 } },
};

export function roleFamily(role: string): RoleFamily {
  const text = role.toLowerCase();
  if (/data|analyst|analytics|scien|\bbi\b|statistic/.test(text)) return "data";
  if (/market|sales|\bhr\b|human resource|business|manager|management|account|finance|operations|executive/.test(text)) return "business";
  return "engineering";
}

const LEVEL_NAMES = { beginner: "Beginner", intermediate: "Intermediate", advanced: "Advanced" } as const;

/** The language for Technical Aptitude: the first one the learner listed. */
function skillLanguage(): "C" | "Java" | "Python" | "SQL" | undefined {
  const languages = ["Python", "Java", "SQL", "C"] as const;
  for (const skill of learnerGoal()?.skills ?? []) {
    const match = languages.find((lang) => lang.toLowerCase() === skill.trim().toLowerCase());
    if (match) return match;
  }
  return undefined;
}

/** One-tap starts built from the learner's role, skills and level. */
function roleStartOptions(): ChatOption[] {
  const goal = learnerGoal();
  if (!goal) return [];
  const role = displayRole(goal.targetRole);
  const family = ROLE_FAMILIES[roleFamily(goal.targetRole)];
  const top = Object.entries(family.mix).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([name]) => name);
  const level = LEVEL_NAMES[beginnerToAdvanced("aptitude_agent")];
  const language = family.focus === "Technical Aptitude" ? skillLanguage() ?? "Python" : undefined;
  return [
    { label: `Mixed test for ${role}`, value: "role_mix", description: `20 questions weighted toward ${top.join(", ")}` },
    { label: `${family.focus} at your level`, value: "role_category", description: `${level}${language ? ` · ${language}` : ""} · what ${role} roles test most` },
  ];
}

const MODE_OPTIONS: ChatOption[] = [{ label: "Mixed Test", value: "mixed" }, { label: "Category Practice", value: "category_practice" }];

/** Practice levels, with the learner's own Aptitude level marked. */
function levelChoices(): ChatOption[] {
  const mine = beginnerToAdvanced("aptitude_agent");
  return levelOptions.map((option) => option.value.toLowerCase() === mine ? { ...option, label: `${option.label} · your level` } : option);
}

/** Languages, with the ones the learner listed as skills first. */
function languageChoices(): ChatOption[] {
  const skills = (learnerGoal()?.skills ?? []).map((skill) => skill.toLowerCase());
  const known = languageOptions.filter((option) => skills.includes(option.value.toLowerCase()));
  const rest = languageOptions.filter((option) => !known.includes(option));
  return [...known.map((option) => ({ ...option, label: `${option.label} · your skill` })), ...rest];
}
const optionMap = (options: Record<string, string>): ChatOption[] => Object.entries(options).map(([value, label]) => ({ value, label: `${value}. ${label}` }));
// The gateway answers 402 "Not enough points" (formerly "Insufficient token balance").
const isTokenInterruption = (error: unknown) => /not enough points|insufficient token balance|token balance/i.test((error as Error)?.message || "");
const resumeOptions = [{ label: "Continue Test", value: "continue test" }];
/** Starting a test can occasionally fail validation on the AI provider's side (a
 * transient generation defect, not a real outage) -- retried once silently before ever
 * bothering the student, and offered one click to retry (with the same configuration,
 * no need to reconfigure) if it still fails. See RETRY_START_TEST below. */
const RETRY_START_TEST = "retry_start_test";
export const createInitialAptitudeState = (): AptitudeFlowState => ({ step: "awaiting_mode" });
export const initialAptitudeMessage = (user: User): AptitudeFlowMessage => ({ text: learnerGoal()
  ? `Hi ${user.name.split(" ")[0]}! Aptitude rounds are a common first filter for ${displayRole(learnerGoal()!.targetRole)} roles. Start with a test built for your role, or choose your own.`
  : `Hi ${user.name.split(" ")[0]}! What would you like to practice?`, options: [...roleStartOptions(), ...MODE_OPTIONS] });

function questionMessage(question: AptitudeQuestion): AptitudeFlowMessage {
  const priority = question.topic_is_starred ? " ★ Priority topic" : "";
  const state = question.status === "answered" ? "Answered" : question.status === "timed_out" ? "Timed out" : "Unanswered";
  return { text: `${question.category} · ${question.topic}${priority} · ${question.difficulty}\n\n${question.sequence}. ${question.question}\n\n${state}${question.status === "unanswered" ? ". Answer before the live timer reaches zero." : ". This question is already submitted."}`, options: question.status === "unanswered" ? optionMap(question.options) : [] };
}
async function startTest(state: AptitudeFlowState, user?: User) {
  // Refresh the agent session immediately before starting. This also
  // upgrades chats that still contain a token issued before the verified
  // DigiDARA identity bridge was introduced.
  if (user) {
    const { sessionToken } = await ensureAptitudeSession(user);
    state = { ...state, sessionToken };
    localStorage.setItem(`digidara_aptitude_token_${user.email.toLowerCase()}`, sessionToken);
  }
  const payload: Record<string, unknown> = { mode: state.mode, technical_language: state.technicalLanguage || "Python" };
  if (state.mode === "category_practice") Object.assign(payload, { category: state.category, level: state.level });
  const created = await createAptitudeTest(state.sessionToken!, payload);
  const question = await getAptitudeQuestion(state.sessionToken!, created.test_id);
  return { state: { ...state, step: "awaiting_question" as const, testId: created.test_id, question, totalQuestions: question.total_questions, hintsRemaining: question.hints_remaining }, messages: [questionMessage(question)] };
}

async function startTestWithRetry(state: AptitudeFlowState, user?: User) {
  try {
    return await startTest(state, user);
  } catch (error) {
    // An insufficient balance is a real, non-transient problem -- retrying changes
    // nothing, so it's left to the caller's normal token-interruption handling.
    if (isTokenInterruption(error)) throw error;
    try {
      return await startTest(state, user);
    } catch (retryError) {
      return {
        state,
        messages: [{
          text: `I could not prepare your test: ${(retryError as Error).message}`,
          options: [{ label: "Try again", value: RETRY_START_TEST }],
        }],
      };
    }
  }
}

export async function openAptitudeChat(user: User) {
  const state = createInitialAptitudeState();
  try { const { sessionToken } = await ensureAptitudeSession(user); localStorage.setItem(`digidara_aptitude_token_${user.email.toLowerCase()}`, sessionToken); return { state: { ...state, sessionToken }, messages: [initialAptitudeMessage(user)] }; }
  catch (error) { return { state, messages: [{ text: `I could not connect to Aptitude: ${(error as Error).message}`, options: [{ label: "Try again", value: "retry" }] }] }; }
}

export async function handleAptitudeText(state: AptitudeFlowState, text: string, user?: User): Promise<{ state: AptitudeFlowState; messages: AptitudeFlowMessage[] }> {
  const value = text.trim();
  try {
    // Reuses the already-chosen mode/category/level/language on `state` -- the student
    // never has to reconfigure the test just because generation failed once.
    if (value === RETRY_START_TEST) return await startTestWithRetry(state, user);
    const restartRequested = /^(?:(?:start|begin|take)\s+(?:a\s+)?(?:new|another)\s+(?:test|practice)|restart(?:\s+(?:test|practice))?|new\s+(?:test|practice))$/i.test(value);
    if (restartRequested) {
      if (state.testId && state.sessionToken && state.step !== "completed") {
        await abandonAptitudeTest(state.sessionToken, state.testId);
      }
      const resetState: AptitudeFlowState = { step: "awaiting_mode", sessionToken: state.sessionToken };
      return {
        state: resetState,
        messages: [{ text: "Your previous attempt has ended. What would you like to practice next?", options: [{ label: "Mixed Test", value: "mixed" }, { label: "Category Practice", value: "category_practice" }] }],
      };
    }
    if (/^exit test$/i.test(value) && state.testId && state.sessionToken && (state.step === "awaiting_question" || state.step === "awaiting_next_question")) {
      const result = await abandonAptitudeTest(state.sessionToken, state.testId);
      if (result.status !== "abandoned") throw new Error("The test could not be exited. Please try again.");
      return {
        state: { step: "awaiting_mode" as const, sessionToken: state.sessionToken },
        messages: [{ text: "Test exited. You can start a new Category or Mixed Test.", options: [{ label: "Mixed Test", value: "mixed" }, { label: "Category Practice", value: "category_practice" }] }],
      };
    }
    if (state.step === "completed" && /download|report|pdf/i.test(value)) {
      const report = await downloadAptitudeReport(state.sessionToken!, state.testId!);
      const binary = Uint8Array.from(atob(report.data), (character) => character.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([binary], { type: "application/pdf" }));
      const link = document.createElement("a"); link.href = url; link.download = report.filename || "aptitude-report.pdf"; link.click(); URL.revokeObjectURL(url);
      return { state, messages: [{ text: "Your Aptitude test report has been downloaded." }] };
    }
    if (state.tokenInterrupted) {
      if (!/continue|resume/i.test(value)) return { state, messages: [{ text: "Top up your points, then choose Continue Test to restore the current question and timer.", options: resumeOptions }] };
      const question = await getAptitudeQuestion(state.sessionToken!, state.testId!);
      return { state: { ...state, step: "awaiting_question" as const, question, tokenInterrupted: false, hintsRemaining: question.hints_remaining, hintText: undefined }, messages: [questionMessage(question)] };
    }
    if (state.step === "awaiting_mode" && (value === "role_mix" || value === "role_category")) {
      const goal = learnerGoal();
      if (goal) {
        const family = ROLE_FAMILIES[roleFamily(goal.targetRole)];
        const technicalLanguage = skillLanguage() ?? "Python";
        if (value === "role_category") {
          const level = LEVEL_NAMES[beginnerToAdvanced("aptitude_agent")];
          return await startTestWithRetry({ ...state, mode: "category_practice", category: family.focus, level, technicalLanguage }, user);
        }
        // The role's mix becomes the learner's Mixed Test setup, then the test starts.
        const config = await getMixedTestConfig(state.sessionToken!);
        await saveMixedTestConfig(state.sessionToken!, config.categories.map((c) => ({
          category_id: c.category_id, question_count: family.mix[c.category_name] ?? 0,
        })));
        return await startTestWithRetry({ ...state, mode: "mixed", technicalLanguage }, user);
      }
    }
    if (state.step === "awaiting_mode") {
      const mode = value.toLowerCase().includes("category") ? "category_practice" : value.toLowerCase().includes("mixed") ? "mixed" : undefined;
      if (!mode) return { state, messages: [{ text: "Choose Mixed Test or Category Practice.", options: [{ label: "Mixed Test", value: "mixed" }, { label: "Category Practice", value: "category_practice" }] }] };
      return mode === "category_practice" ? { state: { ...state, mode, step: "awaiting_category" as const }, messages: [{ text: "Choose a category:", options: categoryOptions }] } : { state: { ...state, mode, step: "awaiting_language" as const }, messages: [{ text: "Choose the Technical Aptitude language (Python is the default):", options: languageChoices() }] };
    }
    if (state.step === "awaiting_category") { const category = categories.find((item) => item.toLowerCase() === value.toLowerCase()); if (!category) return { state, messages: [{ text: "Choose a category from the list.", options: categoryOptions }] }; return { state: { ...state, category, step: "awaiting_level" as const }, messages: [{ text: "Choose a practice level:", options: levelChoices() }] }; }
    if (state.step === "awaiting_level") { const level = (["Beginner", "Intermediate", "Advanced"] as const).find((item) => item.toLowerCase() === value.toLowerCase()); if (!level) return { state, messages: [{ text: "Choose Beginner, Intermediate, or Advanced.", options: levelChoices() }] }; return state.category === "Technical Aptitude" ? { state: { ...state, level, step: "awaiting_language" as const }, messages: [{ text: "Choose a programming language:", options: languageChoices() }] } : await startTestWithRetry({ ...state, level }, user); }
    if (state.step === "awaiting_language") { const language = (["C", "Java", "Python", "SQL"] as const).find((item) => item.toLowerCase() === value.toLowerCase()); if (!language) return { state, messages: [{ text: "Choose C, Java, Python, or SQL.", options: languageChoices() }] }; return await startTestWithRetry({ ...state, technicalLanguage: language }, user); }
    if (state.step === "awaiting_next_question") {
      if (!/retry|question|continue/i.test(value)) {
        return { state, messages: [{ text: "Your previous answer was saved. Retry loading the next question to continue.", options: [{ label: "Retry question", value: "retry question" }] }] };
      }
      const nextQuestion = await getAptitudeQuestion(state.sessionToken!, state.testId!);
      return { state: { ...state, step: "awaiting_question" as const, question: nextQuestion, hintsRemaining: nextQuestion.hints_remaining, hintText: undefined }, messages: [questionMessage(nextQuestion)] };
    }
    if (state.step === "awaiting_question") {
      const navMatch = value.match(/^__aptitude_nav:(\d+)$/);
      if (navMatch) {
        const question = await getAptitudeQuestion(state.sessionToken!, state.testId!, Number(navMatch[1]));
        return { state: { ...state, question, hintsRemaining: question.hints_remaining, hintText: question.hint || undefined }, messages: [questionMessage(question)] };
      }
      if (/^skip(?: question)?$/i.test(value)) {
        const question = await skipAptitudeQuestion(state.sessionToken!, state.testId!);
        return { state: { ...state, question, hintsRemaining: question.hints_remaining, hintText: question.hint || undefined }, messages: [{ text: `Question ${state.question?.sequence} skipped. You can return to it from the question navigator.` }, questionMessage(question)] };
      }
      if (state.question?.status && state.question.status !== "unanswered") return { state, messages: [{ text: "This question is already submitted. Choose another question from the navigator." }] };
      if (value.toLowerCase() === "hint") {
        try {
          const result = await requestAptitudeHint(state.sessionToken!, state.testId!);
          return { state: { ...state, hintsRemaining: result.hints_remaining, hintText: result.hint }, messages: [{ text: `Hint (${result.hints_remaining} remaining): ${result.hint}`, options: optionMap(state.question!.options) }] };
        } catch (error) {
          if (isTokenInterruption(error)) return { state: { ...state, tokenInterrupted: true }, messages: [{ text: "You don't have enough points. Top up your points, then continue this test to restore the current question and timer.", options: resumeOptions }] };
          return { state, messages: [{ text: `I could not generate a safe hint right now: ${(error as Error).message}`, options: optionMap(state.question!.options) }] };
        }
      }
      // Accept only a real answer token. Previously any sentence containing
      // A-D (for example "start a new test") was misread as an answer.
      const timedOut = value === "__aptitude_timeout__";
      const selected = timedOut ? "" : value.match(/^(?:option\s*)?([ABCD])(?:[.)])?$/i)?.[1]?.toUpperCase() || "";
      if (!selected && !timedOut) return { state, messages: [{ text: "Select an answer option, or use the optional hint button above the question.", options: optionMap(state.question!.options) }] };
      const result = await submitAptitudeAnswer(state.sessionToken!, state.testId!, selected, timedOut);
      const verdict = result.timed_out ? "Time expired." : result.is_correct ? "Correct!" : "Not quite.";
      if (result.complete) { const results = await getAptitudeResults(state.sessionToken!, state.testId!); return { state: { ...state, step: "completed" as const, question: undefined, score: Number(results.score ?? 0) }, messages: [{ text: `${verdict}\nCorrect answer: ${result.correct_answer}\n\n${result.explanation}\n\nTest complete. Your score is ${results.score ?? "-"}/${results.total_questions ?? state.totalQuestions}.`, options: [{ label: "Download PDF report", value: "download report" }] }] }; }
      const feedback = `${verdict}\nCorrect answer: ${result.correct_answer}\n\n${result.explanation}`;
      try {
        const nextQuestion = await getAptitudeQuestion(state.sessionToken!, state.testId!);
        return { state: { ...state, question: nextQuestion, hintsRemaining: nextQuestion.hints_remaining, hintText: undefined }, messages: [{ text: feedback }, questionMessage(nextQuestion)] };
      } catch (error) {
        // The answer is already committed. Clear the old question so its
        // answer buttons cannot be submitted again while Question N+1 is
        // being recovered.
        return {
          state: { ...state, step: "awaiting_next_question" as const, question: undefined },
          messages: [
            { text: feedback },
            { text: `Your answer was saved, but the next stored question could not be loaded: ${(error as Error).message}`, options: [{ label: "Retry question", value: "retry question" }] },
          ],
        };
      }
    }
    return { state, messages: [{ text: "This test is complete. Start a new Aptitude chat for another attempt." }] };
  } catch (error) {
    if (isTokenInterruption(error) && state.testId && state.question) {
      return { state: { ...state, tokenInterrupted: true }, messages: [{ text: "You don't have enough points. Top up your points, then continue this test to restore the current question and timer.", options: resumeOptions }] };
    }
    return { state, messages: [{ text: `Aptitude request failed: ${(error as Error).message}` }] };
  }
}
