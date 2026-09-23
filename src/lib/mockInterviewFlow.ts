import type { ChatOption, User } from "../types";
import {
  endMockInterview, ensureMockInterviewSession, exitMockInterview, getActiveMockInterview, startMockInterview, submitMockInterviewAnswer,
  type MockInterviewQuestion, type MockInterviewSummary,
} from "./mockInterviewApi";

export type MockInterviewStep = "choose_round" | "choose_mode" | "choose_role" | "awaiting_role" | "awaiting_subject" | "choose_difficulty" | "in_interview" | "completed" | "error";
export interface MockInterviewFlowState {
  step: MockInterviewStep;
  sessionToken?: string;
  roundType?: "technical" | "hr";
  interviewMode?: "course" | "custom_topic" | "role";
  subject?: string;
  roleName?: string;
  difficulty?: "beginner" | "intermediate" | "advanced";
  interviewId?: number;
  question?: string;
  questionOrder?: number;
  realQuestionIndex?: number;
  totalQuestions?: number;
  summary?: MockInterviewSummary;
  error?: string;
}
export interface MockInterviewMessage { text: string; options?: ChatOption[]; }
export interface MockInterviewFlowResult { state: MockInterviewFlowState; messages: MockInterviewMessage[]; }
export interface MockInterviewAnswerTiming { timeTakenSec: number; timedOut?: boolean; }

export const createInitialMockInterviewState = (): MockInterviewFlowState => ({ step: "choose_round" });

const roundOptions: ChatOption[] = [
  { label: "Technical interview", value: "technical", description: "Practice a job role or technical topic." },
  { label: "HR interview", value: "hr", description: "Practice behavioural and situational questions." },
];
const modeOptions: ChatOption[] = [
  { label: "Job role", value: "role", description: "Questions across the skills for a real job." },
  { label: "Custom topic", value: "custom_topic", description: "Focus on one technical subject." },
];
const roleOptions: ChatOption[] = [
  { label: "Python Fullstack Developer", value: "Python Fullstack Developer" },
  { label: "Data Analyst", value: "Data Analyst" },
  { label: "Digital Marketing Executive", value: "Digital Marketing Executive" },
  { label: "AI Engineer", value: "AI Engineer" },
  { label: "Enter another role", value: "custom_role" },
];
const difficultyOptions: ChatOption[] = [
  { label: "Beginner · 60 seconds", value: "beginner" },
  { label: "Intermediate · 90 seconds", value: "intermediate" },
  { label: "Advanced · 120 seconds", value: "advanced" },
];
const restartOption: ChatOption[] = [{ label: "Start another interview", value: "restart" }];
const exitOption: ChatOption[] = [{ label: "Exit interview", value: "exit_interview", description: "Stop now; unanswered questions will not be scored." }];

const errorText = (error: unknown) => error instanceof Error ? error.message : "Something went wrong.";

function questionMessage(question: string, order: number, total?: number, realIndex?: number): MockInterviewMessage {
  const heading = `Question ${realIndex ?? order}${total ? ` of ${total}` : ""}`;
  return { text: `${heading}:\n\n${question}`, options: exitOption };
}

async function begin(state: MockInterviewFlowState, difficulty: "beginner" | "intermediate" | "advanced"): Promise<MockInterviewFlowResult> {
  try {
    const q: MockInterviewQuestion = await startMockInterview(state.sessionToken!, {
      round_type: state.roundType!,
      interview_mode: state.roundType === "hr" ? "course" : state.interviewMode === "role" ? "role" : "custom_topic",
      ...(state.interviewMode === "role" ? { role_name: state.roleName } : { subject: state.subject }),
      difficulty,
      num_questions: 10,
    });
    const next: MockInterviewFlowState = {
      ...state, step: "in_interview", difficulty: q.difficulty ?? difficulty,
      roundType: q.round_type === "hr" ? "hr" : state.roundType,
      interviewMode: q.interview_mode ?? state.interviewMode,
      roleName: q.role_name ?? state.roleName,
      interviewId: q.interview_id,
      question: q.question, questionOrder: q.question_order,
      realQuestionIndex: q.real_question_index ?? q.question_order,
      totalQuestions: q.total_questions,
      error: undefined,
    };
    const intro = q.resumed_existing ? "Resuming your interview in progress." : "Your interview has started. The question will be read aloud; you can speak or type your answer.";
    return { state: next, messages: [{ text: intro }, questionMessage(q.question, q.question_order, q.total_questions, next.realQuestionIndex)] };
  } catch (error) {
    return { state: { ...state, step: "choose_difficulty", error: errorText(error) }, messages: [{ text: `I couldn't start the interview: ${errorText(error)}`, options: difficultyOptions }] };
  }
}

async function finish(state: MockInterviewFlowState): Promise<MockInterviewFlowResult> {
  try {
    const summary = await endMockInterview(state.sessionToken!, state.interviewId!);
    return {
      state: { ...state, step: "completed", summary, question: undefined },
      messages: [{ text: "Interview complete. Your scores and answer feedback are below. You can download your PDF report here.", options: restartOption }],
    };
  } catch (error) {
    return { state: { ...state, step: "in_interview", question: undefined, error: errorText(error) }, messages: [{ text: `Your answers were saved, but the final report is still processing: ${errorText(error)}`, options: [{ label: "Retry final report", value: "retry_report" }] }] };
  }
}

export async function openMockInterviewChat(user: User): Promise<MockInterviewFlowResult> {
  const state = createInitialMockInterviewState();
  try {
    const session = await ensureMockInterviewSession(user.id, user.name, user.email);
    try {
      const active = await getActiveMockInterview(session.sessionToken);
      if (active.active && active.question && active.interview_id) {
        const resumed: MockInterviewFlowState = {
          step: "in_interview", sessionToken: session.sessionToken,
          roundType: active.round_type === "hr" ? "hr" : "technical",
          interviewMode: active.interview_mode ?? "course",
          roleName: active.role_name ?? undefined,
          difficulty: active.difficulty ?? "intermediate",
          interviewId: active.interview_id, question: active.question,
          questionOrder: active.question_order, realQuestionIndex: active.real_question_index ?? active.question_order,
          totalQuestions: active.total_questions,
        };
        return { state: resumed, messages: [
          { text: "You have an interview in progress. Let's continue where you left off." },
          questionMessage(active.question, active.question_order, active.total_questions, resumed.realQuestionIndex),
        ] };
      }
    } catch { /* Setup remains available if the optional resume check fails. */ }
    return {
      state: { ...state, sessionToken: session.sessionToken },
      messages: [{ text: `Hi ${user.name.split(" ")[0]}! Which mock interview would you like to practise?`, options: roundOptions }],
    };
  } catch (error) {
    return { state: { ...state, step: "error", error: errorText(error) }, messages: [{ text: `I couldn't start Mock Interview: ${errorText(error)}`, options: [{ label: "Try again", value: "retry" }] }] };
  }
}

export async function handleMockInterviewText(state: MockInterviewFlowState, user: User, rawText: string, timing?: MockInterviewAnswerTiming): Promise<MockInterviewFlowResult> {
  const text = rawText.trim();
  const value = text.toLowerCase();

  if (!state.sessionToken) return openMockInterviewChat(user);
  if (value === "restart" || value === "retry" || state.step === "completed" || state.step === "error") return openMockInterviewChat(user);

  if (state.step === "choose_round") {
    if (value === "hr") return { state: { ...state, roundType: "hr", interviewMode: "course", step: "choose_difficulty" }, messages: [{ text: "Choose your HR interview difficulty. This interview has 10 questions.", options: difficultyOptions }] };
    if (value === "technical") return { state: { ...state, roundType: "technical", step: "choose_mode" }, messages: [{ text: "Would you like questions for a job role or one technical topic?", options: modeOptions }] };
    return { state, messages: [{ text: "Please choose an interview type.", options: roundOptions }] };
  }

  if (state.step === "choose_mode") {
    if (value === "role") return { state: { ...state, interviewMode: "role", step: "choose_role" }, messages: [{ text: "Choose a job role or enter your own.", options: roleOptions }] };
    if (value === "custom_topic") return { state: { ...state, interviewMode: "custom_topic", step: "awaiting_subject" }, messages: [{ text: "Which technical topic should I interview you on? For example, Python, React, or MySQL." }] };
    return { state, messages: [{ text: "Choose a job role or custom topic.", options: modeOptions }] };
  }

  if (state.step === "choose_role") {
    if (value === "custom_role") return { state: { ...state, step: "awaiting_role" }, messages: [{ text: "Enter the job role you want to practise (up to 150 characters)." }] };
    const selected = roleOptions.find((option) => option.value.toLowerCase() === value && option.value !== "custom_role");
    if (selected) return { state: { ...state, roleName: selected.value, step: "choose_difficulty" }, messages: [{ text: `Great. Choose a difficulty for the ${selected.value} interview.`, options: difficultyOptions }] };
    return { state, messages: [{ text: "Choose a listed role or select Enter another role.", options: roleOptions }] };
  }

  if (state.step === "awaiting_role" || state.step === "awaiting_subject") {
    if (!text || text.length > 150) return { state, messages: [{ text: "Enter a name of up to 150 characters." }] };
    const next = state.step === "awaiting_role" ? { roleName: text } : { subject: text };
    return { state: { ...state, ...next, step: "choose_difficulty" }, messages: [{ text: `Choose a difficulty for ${text}. This interview has 10 questions.`, options: difficultyOptions }] };
  }

  if (state.step === "choose_difficulty") {
    if (value === "beginner" || value === "intermediate" || value === "advanced") return begin(state, value);
    return { state, messages: [{ text: "Please choose a difficulty.", options: difficultyOptions }] };
  }

  if (state.step === "in_interview" && state.interviewId && state.questionOrder) {
    if (value === "retry_report") return finish(state);
    if (value === "exit_interview") {
      try {
        await exitMockInterview(state.sessionToken, state.interviewId, state.questionOrder);
        return { state: { ...state, step: "completed", question: undefined }, messages: [{ text: "You've exited the interview.", options: restartOption }] };
      } catch (error) {
        return { state, messages: [{ text: `I couldn't exit the interview: ${errorText(error)}`, options: exitOption }] };
      }
    }
    if (!text && !timing?.timedOut) return { state, messages: [{ text: "Speak or type an answer before submitting." }] };
    try {
      const result = await submitMockInterviewAnswer(state.sessionToken, state.interviewId, state.questionOrder, text, timing?.timeTakenSec, timing?.timedOut);
      const verdict = result.answered_question_verdict?.verdict ?? result.verdict;
      const reason = result.answered_question_verdict?.reason ?? result.verdict_reason;
      const feedback: MockInterviewMessage[] = verdict
        ? [{ text: `Answer feedback: ${verdict}${reason ? ` — ${reason}` : ""}` }]
        : [{ text: "Answer saved. Detailed feedback will appear in your final report." }];
      if (result.done || !result.question) {
        const completed = await finish(state);
        return { ...completed, messages: [...feedback, ...completed.messages] };
      }
      const order = result.question_order ?? state.questionOrder + 1;
      const realIndex = result.real_question_index ?? (state.realQuestionIndex ?? state.questionOrder) + 1;
      const next: MockInterviewFlowState = {
        ...state, question: result.question, questionOrder: order, realQuestionIndex: realIndex,
        totalQuestions: result.total_questions ?? state.totalQuestions,
      };
      return { state: next, messages: [...feedback, questionMessage(result.question, order, next.totalQuestions, realIndex)] };
    } catch (error) {
      return { state, messages: [{ text: `I couldn't save that answer: ${errorText(error)} Please retry.` }] };
    }
  }

  return openMockInterviewChat(user);
}
