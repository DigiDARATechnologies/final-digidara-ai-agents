import type { Agent, Chat } from "../types";
import type { AptitudeFlowState } from "./aptitudeFlow";
import type { CapstoneFlowState } from "./capstoneFlow";
import type { CertificateFlowState } from "./certificateAgentFlow";
import type { CodeForgeFlowState } from "./codeforgeFlow";
import type { CommunicationFlowState } from "./communicationFlow";
import type { MockInterviewFlowState } from "./mockInterviewFlow";
import type { ResumeBuilderFlowState } from "./resumeBuilderFlow";

/** A chat's automatic name: what it is about (`subject`) and, once known, how
 * it went (`result`, e.g. an exam score). Shown as "subject · result". */
export interface AutoTitle {
  subject: string;
  result?: string;
}

/** Every agent's flow state, keyed by chat id. */
export interface AgentStates {
  aptitude: Record<string, AptitudeFlowState>;
  capstone: Record<string, CapstoneFlowState>;
  certificate: Record<string, CertificateFlowState>;
  codeforge: Record<string, CodeForgeFlowState>;
  communication: Record<string, CommunicationFlowState>;
  mockInterview: Record<string, MockInterviewFlowState>;
  resumeBuilder: Record<string, ResumeBuilderFlowState>;
}

const MAX_SUBJECT = 60;

function short(text: string, limit = MAX_SUBJECT) {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length > limit ? `${clean.slice(0, limit - 1).trimEnd()}…` : clean;
}

function capitalize(text: string) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

function join(...parts: Array<string | undefined | null | false>) {
  return parts.filter(Boolean).join(" · ");
}

export function formatAutoTitle(title: AutoTitle) {
  return title.result ? `${title.subject} · ${title.result}` : title.subject;
}

/** What a chat with this agent is about, from its flow state -- or undefined
 * until that is known (the chat keeps its first-message name meanwhile). */
export function autoChatTitle(agent: Agent | undefined, chatId: string, states: AgentStates): AutoTitle | undefined {
  switch (agent?.kind) {
    case "resume-builder": {
      const state = states.resumeBuilder[chatId];
      const role = state?.draft?.targetRole?.trim();
      if (!role) return undefined;
      return { subject: short(`Resume · ${capitalize(role)}`), result: state.atsScore !== undefined ? `ATS ${state.atsScore}` : undefined };
    }
    case "certificate": {
      const state = states.certificate[chatId];
      const topic = state?.topic?.trim();
      if (!topic) return undefined;
      const subject = short(/\bexam$/i.test(topic) ? topic : `${topic} Exam`);
      const finished = state.step === "completed" && typeof state.score === "number";
      return { subject, result: finished ? `${Math.round(state.score! * 100) / 100}% ${state.passed ? "✓" : "✗"}` : undefined };
    }
    case "communication": {
      const state = states.communication[chatId];
      if (state?.activeModule === "writing" && state.writingTopic) return { subject: short(`✍️ Writing · ${state.writingTopic}`) };
      if (state?.activeModule === "speaking" && state.promptText) return { subject: short(`🗣️ Speaking · "${short(state.promptText, 34)}"`, 60) };
      if (state?.activeModule === "pronunciation" && state.pronunciationMode) {
        return { subject: short(join("🔤 Pronunciation", capitalize(String(state.pronunciationMode).replace(/_/g, " ")), capitalize(state.difficulty))) };
      }
      return undefined;
    }
    case "mock-interview": {
      const state = states.mockInterview[chatId];
      const focus = state?.roleName || state?.subject;
      if (!focus) return undefined;
      const score = state.step === "completed" ? state.summary?.overall_score : undefined;
      return {
        subject: short(join("Interview", focus, state.difficulty && capitalize(state.difficulty))),
        result: typeof score === "number" ? `${score}/10` : undefined,
      };
    }
    case "capstone": {
      const state = states.capstone[chatId];
      const project = state?.chosenTopic?.title;
      if (!project) return undefined;
      const result = state.step === "graded" && state.passed
        ? `Passed${typeof state.finalScore === "number" ? ` ${state.finalScore}` : ""} ✓`
        : undefined;
      return { subject: short(`Capstone · ${project}`), result };
    }
    case "aptitude": {
      const state = states.aptitude[chatId];
      if (!state?.mode) return undefined;
      const focus = state.mode === "mixed" ? "Mixed" : state.category;
      if (!focus) return undefined;
      const finished = state.step === "completed" && typeof state.score === "number";
      return {
        subject: short(join("Aptitude", focus, state.level, state.technicalLanguage)),
        result: finished ? `${state.score}/${state.totalQuestions ?? "?"}` : undefined,
      };
    }
    case "codeforge": {
      const state = states.codeforge[chatId];
      if (!state?.courseName) return undefined;
      return { subject: short(join("LeetCode", state.courseName, state.topicName)) };
    }
    default:
      return undefined;
  }
}

/** The name a chat gets from its first message (see App's sendMessage). */
export function firstMessageTitle(chat: Chat) {
  const first = chat.messages.find((message) => message.role === "user")?.text.trim();
  if (!first) return undefined;
  return first.length > 42 ? `${first.slice(0, 42)}…` : first;
}

/** The chat's title after applying its automatic name, or undefined when it
 * should stay as it is:
 * - a title the user set by hand is never changed;
 * - a still-default title (the agent's name or the first message) takes the
 *   automatic name;
 * - an automatic title keeps its subject and only gains or updates a result
 *   (e.g. "· 76% ✓"), so it never jumps between subjects. */
export function nextChatTitle(chat: Chat, agent: Agent | undefined, auto: AutoTitle | undefined): Pick<Chat, "title" | "titleSource" | "autoSubject"> | undefined {
  if (!auto || chat.titleSource === "manual") return undefined;
  const isDefault = chat.titleSource === "default"
    || (!chat.titleSource && (chat.title === agent?.name || chat.title === firstMessageTitle(chat)));
  // An automatic title without its marker (e.g. reloaded from the server)
  // is recognised by its subject.
  const subject = chat.autoSubject ?? (chat.title.startsWith(auto.subject) ? auto.subject : undefined);
  if (!isDefault && chat.titleSource !== "auto" && !subject) return undefined;
  if (!isDefault && subject !== auto.subject) return undefined;
  const title = formatAutoTitle(auto);
  if (title === chat.title && chat.titleSource === "auto" && chat.autoSubject === auto.subject) return undefined;
  return { title, titleSource: "auto", autoSubject: auto.subject };
}

/** "Today, 7:02 PM", "Yesterday, 9:15 AM", "Sep 29", "Sep 29, 2025". */
export function formatChatTime(timestamp: number, now = new Date()) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "";
  const time = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (timestamp >= startOfToday) return `Today, ${time}`;
  if (timestamp >= startOfToday - 86_400_000) return `Yesterday, ${time}`;
  const sameYear = date.getFullYear() === now.getFullYear();
  return date.toLocaleDateString([], { month: "short", day: "numeric", ...(sameYear ? {} : { year: "numeric" }) });
}
