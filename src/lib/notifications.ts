import { findAgent } from "../data/agents";
import type { Chat } from "../types";
import type { CapstoneFlowState } from "./capstoneFlow";

/** One "you have something pending" entry for the bell: which agent, what is waiting. */
export interface PendingNotification {
  /** Changes when the agent moves to a new step, so a dismissed notification returns only for new work. */
  key: string;
  id: string;
  chatId: string;
  icon: string;
  agentName: string;
  body: string;
}

/** Only the parts of each agent's saved chat progress the bell needs. */
interface Progress { step: string }
export interface NotificationSources {
  chats: Chat[];
  capstone: Record<string, CapstoneFlowState>;
  codeforge: Record<string, Progress & { problemName?: string }>;
  aptitude: Record<string, Progress & { testId?: string; tokenInterrupted?: boolean }>;
  communication: Record<string, Progress>;
  resumeBuilder: Record<string, Progress>;
  certificate: Record<string, Progress>;
  mockInterview: Record<string, Progress>;
  jobFetch: Record<string, Progress>;
}

const HOUR = 3_600_000;
const DAY = 24 * HOUR;

/** "6 days 4 hours", "3 hours", "40 minutes" -- or null once the moment has passed. */
export function timeLeft(deadlineIso: string, now: number): string | null {
  const ms = new Date(deadlineIso).getTime() - now;
  if (!Number.isFinite(ms) || ms <= 0) return null;
  const days = Math.floor(ms / DAY);
  const hours = Math.floor((ms % DAY) / HOUR);
  const plural = (n: number, unit: string) => `${n} ${unit}${n === 1 ? "" : "s"}`;
  if (days) return hours ? `${plural(days, "day")} ${plural(hours, "hour")}` : plural(days, "day");
  if (hours) return plural(hours, "hour");
  return plural(Math.max(1, Math.ceil(ms / 60_000)), "minute");
}

function capstoneBody(state: CapstoneFlowState, now: number): string | null {
  switch (state.step) {
    case "awaiting_topic_choice":
      return "Choose project A or B to continue.";
    case "awaiting_timer_confirm":
      return "Your project is ready. Confirm to start your 7-day timer.";
    case "awaiting_submission": {
      if (!state.deadlineAt) return null;
      const left = timeLeft(state.deadlineAt, now);
      if (!left) return "The 7-day submission window has closed.";
      return state.revisionNotes
        ? `Revision needed. Fix your project and submit again — ${left} left.`
        : `Your project is pending submission — ${left} left.`;
    }
    case "awaiting_viva_answer":
      return state.vivaRetryPending
        ? `Viva attempt ${(state.vivaAttempt ?? 1) + 1} of ${state.vivaAttemptsTotal ?? 3} is waiting for you.`
        : `Your viva is in progress${state.vivaProgress ? ` — question ${state.vivaProgress}` : ""}. Continue.`;
    case "graded":
      return state.passed ? "Your certificate and final report are ready. Open the chat to get them." : null;
    default:
      return null;
  }
}

/** What is waiting for the student in each agent, from the progress saved in their chats.
 * Only an agent's most recent chat counts, so an old abandoned chat never nags. */
export function buildPendingNotifications(sources: NotificationSources, now: number = Date.now()): PendingNotification[] {
  const latest = new Map<string, Chat>();
  for (const chat of sources.chats) {
    const seen = latest.get(chat.agentId);
    if (!seen || chat.updatedAt > seen.updatedAt) latest.set(chat.agentId, chat);
  }

  const result: PendingNotification[] = [];
  for (const chat of latest.values()) {
    const agent = findAgent(chat.agentId);
    if (!agent?.kind) continue;
    const id = chat.id;
    const step = (sources[({ capstone: "capstone", codeforge: "codeforge", aptitude: "aptitude", communication: "communication", "resume-builder": "resumeBuilder", "mock-interview": "mockInterview", certificate: "certificate", "job-fetch": "jobFetch" } as const)[agent.kind]] as Record<string, Progress>)[id]?.step ?? "";
    let body: string | null = null;
    switch (agent.kind) {
      case "capstone": {
        const state = sources.capstone[id];
        body = state ? capstoneBody(state, now) : null;
        break;
      }
      case "codeforge": {
        const state = sources.codeforge[id];
        if (state && (state.step === "awaiting_code" || state.step === "awaiting_mcq_answer")) {
          body = state.problemName ? `Continue solving “${state.problemName}”.` : "You have a coding problem in progress. Continue.";
        }
        break;
      }
      case "aptitude": {
        const state = sources.aptitude[id];
        if (state && (state.step === "awaiting_question" || state.step === "awaiting_next_question") && state.testId) {
          body = state.tokenInterrupted ? "Your aptitude test is paused — top up tokens to continue." : "Your aptitude test is in progress. Continue.";
        }
        break;
      }
      case "communication": {
        const state = sources.communication[id];
        if (state && ["writing_turn", "writing_chat_turn", "speaking_turn", "pronunciation_turn"].includes(state.step)) {
          body = "Your practice session is in progress. Continue.";
        }
        break;
      }
      case "resume-builder": {
        const state = sources.resumeBuilder[id];
        if (state?.step === "completed") body = "Your ATS resume is ready to download.";
        else if (state && !["choose_workflow", "error"].includes(state.step)) body = "Your resume is in progress. Continue where you left off.";
        break;
      }
      case "mock-interview": {
        const state = sources.mockInterview[id];
        if (state?.step === "in_interview") body = "Your mock interview is in progress. Continue.";
        break;
      }
      case "certificate": {
        const state = sources.certificate[id];
        if (state && ["awaiting_question", "exam_instructions", "awaiting_chat_session"].includes(state.step)) body = "Your certification exam is in progress. Continue.";
        else if (state && (state.step.startsWith("awaiting_certificate") || state.step.startsWith("confirming_certificate"))) body = "Finish your certificate details to get it.";
        break;
      }
      case "job-fetch": {
        const state = sources.jobFetch[id];
        if (state?.step.startsWith("collecting_")) body = "Finish your job preferences to see matching jobs.";
        break;
      }
    }
    if (body) result.push({ key: `${id}:${step}`, id, chatId: chat.id, icon: agent.icon, agentName: agent.name, body });
  }
  return result;
}
