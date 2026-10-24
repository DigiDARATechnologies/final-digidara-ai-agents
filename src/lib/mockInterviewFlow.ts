import type { ChatOption, User } from "../types";
import {
  endMockInterview, ensureMockInterviewSession, exitMockInterview, getActiveMockInterview, startMockInterview, submitMockInterviewAnswer,
  type MockInterviewExit, type MockInterviewQuestion, type MockInterviewSummary,
} from "./mockInterviewApi";
import { beginnerToAdvanced, displayRole, learnerGoal } from "./learnerContext";
import { levelDifficulty, takeAssessmentLaunch, type AssessmentLaunch } from "./proctoring";

export type MockInterviewStep = "choose_round" | "choose_mode" | "choose_role" | "awaiting_role" | "awaiting_subject" | "choose_difficulty" | "choose_question_count" | "in_interview" | "completed" | "error";
export interface MockInterviewFlowState {
  step: MockInterviewStep;
  sessionToken?: string;
  roundType?: "technical" | "hr";
  interviewMode?: "course" | "custom_topic" | "role" | "weak_topic_practice";
  subject?: string;
  roleName?: string;
  difficulty?: "beginner" | "intermediate" | "advanced";
  questionCount?: 5 | 10 | 15;
  interviewId?: number;
  question?: string;
  questionOrder?: number;
  realQuestionIndex?: number;
  totalQuestions?: number;
  summary?: MockInterviewSummary;
  error?: string;
  /** An assessment link's attempt: the interview is proctored with its settings. */
  proctorSessionId?: string;
  assessmentTitle?: string;
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
const questionCountOptions: ChatOption[] = [
  { label: "5 questions", value: "5", description: "Focused practice session." },
  { label: "10 questions", value: "10", description: "Complete interview practice session." },
  { label: "15 questions", value: "15", description: "Extended interview practice session." },
];
const restartOption: ChatOption[] = [{ label: "Start another interview", value: "restart" }];
const exitOption: ChatOption[] = [{ label: "Exit interview", value: "exit_interview", description: "Stop now; unanswered questions will not be scored." }];

const errorText = (error: unknown) => error instanceof Error ? error.message : "Something went wrong.";


const SKILL_PREFIX = "skill:";
const MAX_SKILL_ROUNDS = 4;

/** The opening choices. With a target role, every round is built from it and
 * the learner's skills only: the role's technical round, one round per skill,
 * and the HR round for the role. */
function openingOptions(): ChatOption[] {
  const goal = learnerGoal();
  if (!goal) return roundOptions;
  const role = displayRole(goal.targetRole);
  const skills = goal.skills.map((skill) => skill.trim()).filter(Boolean);
  return [
    { label: `Technical interview for ${role}`, value: "profile_role",
      description: skills.length ? `Your target role · ${skills.slice(0, 4).join(", ")}` : "Your target role" },
    ...skills.slice(0, MAX_SKILL_ROUNDS).map((skill) => ({
      label: `${displayRole(skill)} interview`, value: `${SKILL_PREFIX}${skill}`, description: `One of your skills, as asked for ${role} roles`,
    })),
    { label: `HR interview for ${role}`, value: "hr", description: "Behavioural and situational questions for your target role." },
  ];
}

/** Every interview runs at the learner's Job Readiness level: no choice is shown. */
function learnerDifficulty(): "beginner" | "intermediate" | "advanced" {
  return beginnerToAdvanced("mock_interview_agent");
}

const HOW_MANY = "How many questions would you like?";

/** Role choices with the learner's target role first. */
function roleChoices(): ChatOption[] {
  const goal = learnerGoal();
  if (!goal) return roleOptions;
  const role = displayRole(goal.targetRole);
  const others = roleOptions.filter((option) => option.value.toLowerCase() !== role.toLowerCase());
  return [{ label: `${role} (your target role)`, value: role }, ...others];
}


function questionMessage(question: string, order: number, total?: number, realIndex?: number): MockInterviewMessage {
  const heading = `Question ${realIndex ?? order}${total ? ` of ${total}` : ""}`;
  return { text: `${heading}:\n\n${question}`, options: exitOption };
}

async function begin(state: MockInterviewFlowState, difficulty: "beginner" | "intermediate" | "advanced", questionCount: 5 | 10 | 15 = 10): Promise<MockInterviewFlowResult> {
  try {
    const q: MockInterviewQuestion = await startMockInterview(state.sessionToken!, {
      round_type: state.roundType!,
      interview_mode: state.roundType === "hr" ? "course" : state.interviewMode === "role" ? "role" : "custom_topic",
      ...(state.interviewMode === "role" ? { role_name: state.roleName } : { subject: state.subject }),
      difficulty,
      num_questions: questionCount,
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
      questionCount,
      error: undefined,
    };
    const intro = q.resumed_existing ? "Resuming your interview in progress." : "Your interview has started. The question will be read aloud; you can speak or type your answer.";
    return { state: next, messages: [{ text: intro }, questionMessage(q.question, q.question_order, q.total_questions, next.realQuestionIndex)] };
  } catch (error) {
    return { state: { ...state, step: "choose_question_count", error: errorText(error) }, messages: [{ text: `I couldn't start the interview: ${errorText(error)}. ${HOW_MANY}`, options: questionCountOptions }] };
  }
}

const VERDICT_LABEL: Record<string, string> = { correct: "Correct", partial: "Partly correct", wrong: "Incorrect" };

/** The score for the questions answered before an exit, one line each. */
export function exitScoreText(exited: MockInterviewExit, totalQuestions?: number): string {
  if (exited.score_unavailable) return "Your answers were saved, but they could not be scored right now.";
  const answered = exited.scorecard ?? [];
  if (!answered.length) return "No questions were answered, so there is no score.";
  const marks = Number(exited.total_marks ?? 0);
  const out = Number(exited.max_marks ?? answered.length);
  const lines = answered.map((item, index) => {
    const verdict = VERDICT_LABEL[item.verdict ?? ""] ?? "Not scored";
    return `**Q${index + 1}.** ${item.question ?? ""}\n${verdict}${item.verdict_reason ? ` - ${item.verdict_reason}` : ""}`;
  });
  const of = totalQuestions ? ` of ${totalQuestions}` : "";
  return [`**Your score: ${Number.isInteger(marks) ? marks : marks.toFixed(1)} / ${out}** (${answered.length}${of} questions answered; unanswered questions are not scored)`, ...lines].join("\n\n");
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

/** Runs an assessment link's interview at once, with the organization's
 * settings (the gateway applies them too, whatever is sent from here). */
async function beginAssessment(sessionToken: string, launch: AssessmentLaunch): Promise<MockInterviewFlowResult> {
  try {
    const active = await getActiveMockInterview(sessionToken);
    // Only one interview runs at a time: a practice interview left open is closed first.
    if (active.active && active.interview_id) await exitMockInterview(sessionToken, active.interview_id, active.question_order).catch(() => undefined);
  } catch { /* Nothing open. */ }
  const { config } = launch;
  const state: MockInterviewFlowState = {
    step: "choose_question_count", sessionToken,
    roundType: config.round_type,
    interviewMode: config.round_type === "hr" ? "course" : config.role_name ? "role" : "custom_topic",
    roleName: config.role_name || undefined,
    subject: config.subject || undefined,
    proctorSessionId: launch.sessionId,
    assessmentTitle: launch.title,
  };
  const result = await begin(state, levelDifficulty(config.level), config.num_questions);
  if (result.state.step !== "in_interview") {
    return { state: { ...result.state, step: "error" }, messages: [{ text: `I couldn't start the assessment "${launch.title}": ${result.state.error ?? "please try again"}. Open the assessment link again to retry.` }] };
  }
  return { state: result.state, messages: [{ text: `Assessment: **${launch.title}**. This interview is proctored. Good luck!` }, ...result.messages] };
}

export async function openMockInterviewChat(user: User): Promise<MockInterviewFlowResult> {
  const state = createInitialMockInterviewState();
  const launch = takeAssessmentLaunch();
  try {
    const session = await ensureMockInterviewSession(user.id, user.name, user.email);
    if (launch) return beginAssessment(session.sessionToken, launch);
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
          questionCount: active.total_questions === 5 || active.total_questions === 10 || active.total_questions === 15
            ? active.total_questions : undefined,
        };
        return { state: resumed, messages: [
          { text: "You have an interview in progress. Let's continue where you left off." },
          questionMessage(active.question, active.question_order, active.total_questions, resumed.realQuestionIndex),
        ] };
      }
    } catch { /* Setup remains available if the optional resume check fails. */ }
    return {
      state: { ...state, sessionToken: session.sessionToken },
      messages: [{
        text: learnerGoal()
          ? `Hi ${user.name.split(" ")[0]}! Ready to practise for your ${displayRole(learnerGoal()!.targetRole)} interview? Pick an option.`
          : `Hi ${user.name.split(" ")[0]}! Which mock interview would you like to practise?`,
        options: openingOptions(),
      }],
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
    const goal = learnerGoal();
    const difficulty = learnerDifficulty();
    if (value === "profile_role" && goal) {
      return {
        state: { ...state, roundType: "technical", interviewMode: "role", roleName: displayRole(goal.targetRole), difficulty, step: "choose_question_count" },
        messages: [{ text: `${displayRole(goal.targetRole)} interview. ${HOW_MANY}`, options: questionCountOptions }],
      };
    }
    if (value.startsWith(SKILL_PREFIX) && goal) {
      const skill = text.slice(SKILL_PREFIX.length).trim();
      if (skill) {
        return {
          state: { ...state, roundType: "technical", interviewMode: "custom_topic", subject: skill, difficulty, step: "choose_question_count" },
          messages: [{ text: `${displayRole(skill)} interview for ${displayRole(goal.targetRole)} roles. ${HOW_MANY}`, options: questionCountOptions }],
        };
      }
    }
    if (value === "hr") return { state: { ...state, roundType: "hr", interviewMode: "course", difficulty, step: "choose_question_count" }, messages: [{ text: `HR interview${goal ? ` for ${displayRole(goal.targetRole)} roles` : ""}. ${HOW_MANY}`, options: questionCountOptions }] };
    if (value === "technical") return { state: { ...state, roundType: "technical", step: "choose_mode" }, messages: [{ text: "Would you like questions for a job role or one technical topic?", options: modeOptions }] };
    return { state, messages: [{ text: "Please choose an interview type.", options: openingOptions() }] };
  }

  if (state.step === "choose_mode") {
    if (value === "role") return { state: { ...state, interviewMode: "role", step: "choose_role" }, messages: [{ text: "Choose a job role or enter your own.", options: roleChoices() }] };
    if (value === "custom_topic") return { state: { ...state, interviewMode: "custom_topic", step: "awaiting_subject" }, messages: [{ text: "Which technical topic should I interview you on? For example, Python, React, or MySQL." }] };
    return { state, messages: [{ text: "Choose a job role or custom topic.", options: modeOptions }] };
  }

  if (state.step === "choose_role") {
    if (value === "custom_role") return { state: { ...state, step: "awaiting_role" }, messages: [{ text: "Enter the job role you want to practise (up to 150 characters)." }] };
    const selected = roleChoices().find((option) => option.value.toLowerCase() === value && option.value !== "custom_role");
    if (selected) return { state: { ...state, roleName: selected.value, difficulty: learnerDifficulty(), step: "choose_question_count" }, messages: [{ text: `Great. ${selected.value} interview. ${HOW_MANY}`, options: questionCountOptions }] };
    return { state, messages: [{ text: "Choose a listed role or select Enter another role.", options: roleChoices() }] };
  }

  if (state.step === "awaiting_role" || state.step === "awaiting_subject") {
    if (!text || text.length > 150) return { state, messages: [{ text: "Enter a name of up to 150 characters." }] };
    const next = state.step === "awaiting_role" ? { roleName: text } : { subject: text };
    return { state: { ...state, ...next, difficulty: learnerDifficulty(), step: "choose_question_count" }, messages: [{ text: `${text} interview. ${HOW_MANY}`, options: questionCountOptions }] };
  }

  if (state.step === "choose_difficulty") {
    // A chat saved before levels were automatic: carry on at the learner's level.
    return { state: { ...state, difficulty: learnerDifficulty(), step: "choose_question_count" }, messages: [{ text: HOW_MANY, options: questionCountOptions }] };
  }

  if (state.step === "choose_question_count") {
    if (value === "5" || value === "10" || value === "15") {
      const questionCount = Number(value) as 5 | 10 | 15;
      return begin({ ...state, questionCount }, state.difficulty ?? learnerDifficulty(), questionCount);
    }
    return { state, messages: [{ text: "Choose 5, 10, or 15 questions.", options: questionCountOptions }] };
  }

  if (state.step === "in_interview" && state.interviewId && state.questionOrder) {
    if (value === "retry_report") return finish(state);
    if (value === "exit_interview" || value === "exit_interview_inactive") {
      try {
        const exited = await exitMockInterview(state.sessionToken, state.interviewId, state.questionOrder);
        const reason = value === "exit_interview_inactive"
          ? "The interview has ended because no answer was heard: nothing was said for 30 seconds after the question, or for 15 seconds after I asked \"Hey, are you there?\". Unanswered questions are not scored. Start a new interview whenever you're ready."
          : "You've exited the interview.";
        const text = [reason, exitScoreText(exited, state.totalQuestions)].filter(Boolean).join("\n\n");
        return { state: { ...state, step: "completed", question: undefined }, messages: [{ text, options: restartOption }] };
      } catch (error) {
        return { state, messages: [{ text: `I couldn't exit the interview: ${errorText(error)}`, options: exitOption }] };
      }
    }
    if (!text && !timing?.timedOut) return { state, messages: [{ text: "Speak or type an answer before submitting." }] };
    try {
      const result = await submitMockInterviewAnswer(state.sessionToken, state.interviewId, state.questionOrder, text, timing?.timeTakenSec, timing?.timedOut);
      // Evaluation is performed in the final batch. Keep every turn's UI
      // consistent even if an older backend happens to return an immediate
      // verdict for one answer.
      const feedback: MockInterviewMessage[] = [{
        text: timing?.timedOut
          ? "Time expired - no answer submitted."
          : "Answer saved. Detailed feedback will appear in your final report.",
      }];
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
