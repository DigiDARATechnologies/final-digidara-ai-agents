import type { ChatOption, User } from "../types";
import { abandonAptitudeTest, createAptitudeTest, ensureAptitudeSession, getAptitudeQuestion, getAptitudeResults, requestAptitudeHint, submitAptitudeAnswer, downloadAptitudeReport, type AptitudeQuestion } from "./aptitudeApi";

export type AptitudeStep = "awaiting_mode" | "awaiting_category" | "awaiting_level" | "awaiting_language" | "awaiting_question" | "awaiting_next_question" | "completed";
export interface AptitudeFlowState { step: AptitudeStep; mode?: "mixed" | "category_practice"; category?: string; level?: "Beginner" | "Intermediate" | "Advanced"; technicalLanguage?: "C" | "Java" | "Python" | "SQL"; sessionToken?: string; testId?: string; question?: AptitudeQuestion; score?: number; totalQuestions?: number; hintsRemaining?: number; hintText?: string; }
export interface AptitudeFlowMessage { text: string; options?: ChatOption[]; }
const categories = ["Quantitative Aptitude", "Logical Reasoning", "Verbal Ability", "Analytical Reasoning", "Computer Fundamentals", "Technical Aptitude"];
const categoryOptions = categories.map((value) => ({ label: value, value }));
const levelOptions = ["Beginner", "Intermediate", "Advanced"].map((value) => ({ label: value, value }));
const languageOptions = ["Python", "Java", "C", "SQL"].map((value) => ({ label: value, value }));
const optionMap = (options: Record<string, string>): ChatOption[] => Object.entries(options).map(([value, label]) => ({ value, label: `${value}. ${label}` }));
export const createInitialAptitudeState = (): AptitudeFlowState => ({ step: "awaiting_mode" });
export const initialAptitudeMessage = (user: User): AptitudeFlowMessage => ({ text: `Hi ${user.name.split(" ")[0]}! What would you like to practice?`, options: [{ label: "Mixed Test", value: "mixed" }, { label: "Category Practice", value: "category_practice" }] });

function questionMessage(question: AptitudeQuestion): AptitudeFlowMessage {
  const priority = question.topic_is_starred ? " ★ Priority topic" : "";
  return { text: `Question ${question.sequence}/${question.total_questions} · ${question.category} · ${question.topic}${priority} · ${question.difficulty}\n\n${question.question}\n\nAnswer before the live timer reaches zero.`, options: optionMap(question.options) };
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

export async function openAptitudeChat(user: User) {
  const state = createInitialAptitudeState();
  try { const { sessionToken } = await ensureAptitudeSession(user); localStorage.setItem(`digidara_aptitude_token_${user.email.toLowerCase()}`, sessionToken); return { state: { ...state, sessionToken }, messages: [initialAptitudeMessage(user)] }; }
  catch (error) { return { state, messages: [{ text: `I could not connect to Aptitude: ${(error as Error).message}`, options: [{ label: "Try again", value: "retry" }] }] }; }
}

export async function handleAptitudeText(state: AptitudeFlowState, text: string, user?: User) {
  const value = text.trim();
  try {
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
    if (state.step === "completed" && /download|report|pdf/i.test(value)) {
      const report = await downloadAptitudeReport(state.sessionToken!, state.testId!);
      const binary = Uint8Array.from(atob(report.data), (character) => character.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([binary], { type: "application/pdf" }));
      const link = document.createElement("a"); link.href = url; link.download = report.filename || "aptitude-report.pdf"; link.click(); URL.revokeObjectURL(url);
      return { state, messages: [{ text: "Your Aptitude test report has been downloaded." }] };
    }
    if (state.step === "awaiting_mode") {
      const mode = value.toLowerCase().includes("category") ? "category_practice" : value.toLowerCase().includes("mixed") ? "mixed" : undefined;
      if (!mode) return { state, messages: [{ text: "Choose Mixed Test or Category Practice.", options: [{ label: "Mixed Test", value: "mixed" }, { label: "Category Practice", value: "category_practice" }] }] };
      return mode === "category_practice" ? { state: { ...state, mode, step: "awaiting_category" as const }, messages: [{ text: "Choose a category:", options: categoryOptions }] } : { state: { ...state, mode, step: "awaiting_language" as const }, messages: [{ text: "Choose the Technical Aptitude language (Python is the default):", options: languageOptions }] };
    }
    if (state.step === "awaiting_category") { const category = categories.find((item) => item.toLowerCase() === value.toLowerCase()); if (!category) return { state, messages: [{ text: "Choose a category from the list.", options: categoryOptions }] }; return { state: { ...state, category, step: "awaiting_level" as const }, messages: [{ text: "Choose a practice level:", options: levelOptions }] }; }
    if (state.step === "awaiting_level") { const level = (["Beginner", "Intermediate", "Advanced"] as const).find((item) => item.toLowerCase() === value.toLowerCase()); if (!level) return { state, messages: [{ text: "Choose Beginner, Intermediate, or Advanced.", options: levelOptions }] }; return state.category === "Technical Aptitude" ? { state: { ...state, level, step: "awaiting_language" as const }, messages: [{ text: "Choose a programming language:", options: languageOptions }] } : startTest({ ...state, level }, user); }
    if (state.step === "awaiting_language") { const language = (["C", "Java", "Python", "SQL"] as const).find((item) => item.toLowerCase() === value.toLowerCase()); if (!language) return { state, messages: [{ text: "Choose C, Java, Python, or SQL.", options: languageOptions }] }; return startTest({ ...state, technicalLanguage: language }, user); }
    if (state.step === "awaiting_next_question") {
      if (!/retry|question|continue/i.test(value)) {
        return { state, messages: [{ text: "Your previous answer was saved. Retry loading the next question to continue.", options: [{ label: "Retry question", value: "retry question" }] }] };
      }
      const nextQuestion = await getAptitudeQuestion(state.sessionToken!, state.testId!);
      return { state: { ...state, step: "awaiting_question" as const, question: nextQuestion, hintsRemaining: nextQuestion.hints_remaining, hintText: undefined }, messages: [questionMessage(nextQuestion)] };
    }
    if (state.step === "awaiting_question") {
      if (value.toLowerCase() === "hint") { const result = await requestAptitudeHint(state.sessionToken!, state.testId!); return { state: { ...state, hintsRemaining: result.hints_remaining, hintText: result.hint }, messages: [{ text: `Hint (${result.hints_remaining} remaining): ${result.hint}`, options: optionMap(state.question!.options) }] }; }
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
            { text: `Your answer was saved, but the next question could not be prepared: ${(error as Error).message}`, options: [{ label: "Retry question", value: "retry question" }] },
          ],
        };
      }
    }
    return { state, messages: [{ text: "This test is complete. Start a new Aptitude chat for another attempt." }] };
  } catch (error) { return { state, messages: [{ text: `Aptitude request failed: ${(error as Error).message}` }] }; }
}
