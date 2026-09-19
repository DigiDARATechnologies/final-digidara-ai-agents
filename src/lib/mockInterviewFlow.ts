import type { ChatOption, User } from "../types";
import {
  endMockInterview, ensureMockInterviewSession, exitMockInterview, startMockInterview, submitMockInterviewAnswer,
  type MockInterviewQuestion,
} from "./mockInterviewApi";

export type MockInterviewStep = "choose_round" | "awaiting_subject" | "choose_difficulty" | "in_interview" | "completed" | "error";
export interface MockInterviewFlowState {
  step: MockInterviewStep;
  sessionToken?: string;
  roundType?: "technical" | "hr";
  subject?: string;
  interviewId?: number;
  questionOrder?: number;
  totalQuestions?: number;
  error?: string;
}
export interface MockInterviewMessage { text: string; options?: ChatOption[]; }
export interface MockInterviewFlowResult { state: MockInterviewFlowState; messages: MockInterviewMessage[]; }

export const createInitialMockInterviewState = (): MockInterviewFlowState => ({ step: "choose_round" });

const roundOptions: ChatOption[] = [
  { label: "Technical interview", value: "technical", description: "Questions on a subject or topic you choose." },
  { label: "HR interview", value: "hr", description: "Behavioural and situational questions." },
];
const difficultyOptions: ChatOption[] = [
  { label: "Beginner", value: "beginner" },
  { label: "Intermediate", value: "intermediate" },
  { label: "Advanced", value: "advanced" },
];
const restartOption: ChatOption[] = [{ label: "Start a new interview", value: "restart" }];
const exitOption: ChatOption[] = [{ label: "Exit interview", value: "exit_interview", description: "Stop now; unanswered questions won't be scored." }];

const errorText = (error: unknown) => (error as Error).message || "Something went wrong.";

function questionMessage(question: string, order: number, total?: number): MockInterviewMessage {
  return { text: `Question ${order}${total ? ` of ${total}` : ""}:\n\n${question}\n\nType your answer below.`, options: exitOption };
}

async function begin(state: MockInterviewFlowState, difficulty: string): Promise<MockInterviewFlowResult> {
  try {
    const q: MockInterviewQuestion = await startMockInterview(state.sessionToken!, {
      round_type: state.roundType!, subject: state.subject, difficulty,
    });
    const next: MockInterviewFlowState = {
      ...state, step: "in_interview", interviewId: q.interview_id, questionOrder: q.question_order, totalQuestions: q.total_questions, error: undefined,
    };
    const intro = q.resumed_existing ? "Resuming the interview you already had in progress." : "Your interview has started.";
    return { state: next, messages: [{ text: intro }, questionMessage(q.question, q.question_order, q.total_questions)] };
  } catch (error) {
    return { state: { ...state, step: "choose_difficulty", error: errorText(error) }, messages: [{ text: `I couldn't start the interview: ${errorText(error)}`, options: difficultyOptions }] };
  }
}

async function finish(state: MockInterviewFlowState): Promise<MockInterviewFlowResult> {
  try {
    const summary = await endMockInterview(state.sessionToken!, state.interviewId!);
    const score = summary.total_marks !== undefined && summary.max_marks ? `Score: ${summary.total_marks} / ${summary.max_marks}` : "Your interview is complete.";
    return { state: { ...state, step: "completed" }, messages: [{ text: `${score}\n\nOpen your history to review each answer and download the PDF report.`, options: restartOption }] };
  } catch (error) {
    return { state: { ...state, step: "in_interview", error: errorText(error) }, messages: [{ text: `I couldn't finish the interview yet: ${errorText(error)}` }] };
  }
}

export async function openMockInterviewChat(user: User): Promise<MockInterviewFlowResult> {
  const state = createInitialMockInterviewState();
  try {
    const session = await ensureMockInterviewSession(user.id, user.name, user.email);
    return {
      state: { ...state, sessionToken: session.sessionToken },
      messages: [{ text: `Hi ${user.name.split(" ")[0]}! Ready for a mock interview? Which round would you like to practise?`, options: roundOptions }],
    };
  } catch (error) {
    return { state: { ...state, step: "error", error: errorText(error) }, messages: [{ text: `I couldn't start Mock Interview: ${errorText(error)}`, options: [{ label: "Try again", value: "retry" }] }] };
  }
}

export async function handleMockInterviewText(state: MockInterviewFlowState, user: User, rawText: string): Promise<MockInterviewFlowResult> {
  const text = rawText.trim();
  const value = text.toLowerCase();

  if (!state.sessionToken) return openMockInterviewChat(user);

  if (value === "restart" || value === "retry" || state.step === "completed" || state.step === "error") {
    return openMockInterviewChat(user);
  }

  if (state.step === "choose_round") {
    if (value === "technical" || value === "hr") {
      const roundType = value as "technical" | "hr";
      if (roundType === "hr") return { state: { ...state, roundType, step: "choose_difficulty" }, messages: [{ text: "How challenging should the HR interview be?", options: difficultyOptions }] };
      return { state: { ...state, roundType, step: "awaiting_subject" }, messages: [{ text: "Which subject or topic should I interview you on? (for example: Python, React, MySQL)" }] };
    }
    return { state, messages: [{ text: "Please choose a round to begin.", options: roundOptions }] };
  }

  if (state.step === "awaiting_subject") {
    if (!text || text.length > 150) return { state, messages: [{ text: "Please enter a topic of up to 150 characters." }] };
    return { state: { ...state, subject: text, step: "choose_difficulty" }, messages: [{ text: `Great — ${text}. How challenging should it be?`, options: difficultyOptions }] };
  }

  if (state.step === "choose_difficulty") {
    if (["beginner", "intermediate", "advanced"].includes(value)) return begin(state, value);
    return { state, messages: [{ text: "Please choose a difficulty.", options: difficultyOptions }] };
  }

  if (state.step === "in_interview" && state.interviewId && state.questionOrder && state.sessionToken) {
    if (value === "exit_interview") {
      try { await exitMockInterview(state.sessionToken, state.interviewId, state.questionOrder); } catch { /* the interview is abandoned either way */ }
      return { state: { ...state, step: "completed" }, messages: [{ text: "You've exited the interview.", options: restartOption }] };
    }
    try {
      const result = await submitMockInterviewAnswer(state.sessionToken, state.interviewId, state.questionOrder, text);
      const feedback: MockInterviewMessage[] = result.verdict ? [{ text: `Feedback: ${result.verdict}${result.verdict_reason ? ` — ${result.verdict_reason}` : ""}` }] : [];
      if (result.done || !result.question) return finish(state).then((r) => ({ ...r, messages: [...feedback, ...r.messages] }));
      const order = result.question_order ?? state.questionOrder + 1;
      return {
        state: { ...state, questionOrder: order, totalQuestions: result.total_questions ?? state.totalQuestions },
        messages: [...feedback, questionMessage(result.question, order, result.total_questions ?? state.totalQuestions)],
      };
    } catch (error) {
      return { state, messages: [{ text: `I couldn't record that answer: ${errorText(error)} Please try sending it again.` }] };
    }
  }

  return openMockInterviewChat(user);
}
