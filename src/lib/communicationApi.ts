import { gatewayInvokeUrl, invokeAgent } from "./gatewayClient";

const INVOKE_URL = gatewayInvokeUrl(import.meta.env.VITE_COMMUNICATION_AGENT_NAME, "communication_agent");

function invoke<T>(action: string, payload: Record<string, unknown> = {}): Promise<T> {
  return invokeAgent<T>(INVOKE_URL, action, payload);
}

export async function checkCommunicationHealth(): Promise<boolean> {
  try {
    const result = await invoke<{ status: string }>("health");
    return result.status === "ok";
  } catch {
    return false;
  }
}

export interface CommunicationUser {
  id: number;
  name: string;
  email: string;
  total_xp: number;
}

export interface BridgeIdentityResult {
  user: CommunicationUser;
  authToken: string;
}

export function bridgeIdentity(name: string, email: string) {
  return invoke<BridgeIdentityResult>("bridge_identity", { name, email });
}

export type Difficulty = "easy" | "medium" | "hard";

export interface DashboardData {
  sessions_completed: number;
  overall_score: number | null;
  speaking_average: number | null;
  speaking_completed: number;
  writing_average: number | null;
  writing_completed: number;
  pronunciation_average: number | null;
  pronunciation_completed: number;
  best_skill: { label: string; average: number | null };
  needs_work: { label: string; average: number | null };
  recent_activity: Array<Record<string, any>>;
  [key: string]: any;
}

export function getDashboard(authToken: string) {
  return invoke<DashboardData>("dashboard", { authToken });
}

export function getDailyChallengeToday(authToken: string) {
  return invoke<Record<string, any>>("daily_challenge_today", { authToken });
}

export function getHistory(authToken: string, page = 1) {
  return invoke<{ items: Array<Record<string, any>>; pagination: Record<string, any> }>("history_list", {
    authToken,
    page,
    per_page: 10,
  });
}

// ── Writing ────────────────────────────────────────────────────────────────

export interface WritingTurnResult {
  session_id: number;
  turn_id?: number;
  submitted_turn_id?: number;
  turn_number: number;
  total_turns: number;
  prompt?: string;
  mode: string;
  difficulty: string;
  topic_title?: string;
  done?: boolean;
  feedback?: {
    short_feedback?: string;
    feedback?: string;
    scores?: Record<string, number | null>;
    corrected_answer?: string;
    better_natural_answer?: string;
    mistakes?: Array<{ incorrect?: string; correct?: string; explanation?: string }>;
  };
  last_turn_scores?: Record<string, any>;
}

export function startWriting(
  authToken: string,
  opts: { mode: "topic" | "daily"; difficulty: Difficulty; topicTitle?: string; topicDescription?: string },
) {
  return invoke<WritingTurnResult>("writing_start", {
    authToken,
    mode: opts.mode,
    difficulty: opts.difficulty,
    topic_source: opts.mode === "topic" ? "custom" : undefined,
    topic_title: opts.topicTitle,
    topic_description: opts.topicDescription,
  });
}

export function respondWriting(authToken: string, sessionId: number, answer: string, finalizeAfterSubmission = false) {
  return invoke<WritingTurnResult>("writing_respond", {
    authToken, session_id: sessionId, answer, finalize_after_submission: finalizeAfterSubmission,
  });
}

export function endWriting(authToken: string, sessionId: number) {
  return invoke<Record<string, any>>("writing_end", { authToken, session_id: sessionId });
}

export function writingChat(
  authToken: string,
  topic: string,
  difficulty: Difficulty,
  history: Array<{ role: "assistant" | "user"; text: string }>,
) {
  return invoke<{ reply: string; reaction?: string; next_question?: string; corrected_answer?: string | null }>("writing_chat", { authToken, topic, difficulty, history });
}

// ── Speaking ───────────────────────────────────────────────────────────────

export interface SpeakingTurnResult {
  session_id: number;
  turn_number?: number;
  total_turns?: number;
  next_question?: string;
  done?: boolean;
  feedback?: {
    scores?: Record<string, number | null>;
    explanation?: string;
    status?: string;
    reaction?: string;
    corrected_answer?: string | null;
  };
  summary?: Record<string, any>;
}

export function startSpeaking(
  authToken: string,
  opts: { mode: "topic" | "daily"; difficulty: Difficulty; topicTitle?: string; topicDescription?: string },
) {
  return invoke<Record<string, any>>("speaking_start", {
    authToken,
    mode: opts.mode,
    difficulty: opts.difficulty,
    topic_source: opts.mode === "topic" ? "custom" : undefined,
    topic_title: opts.topicTitle,
    topic_description: opts.topicDescription,
  });
}

export function respondSpeaking(authToken: string, sessionId: number, answer: string) {
  return invoke<SpeakingTurnResult>("speaking_respond", { authToken, session_id: sessionId, answer });
}

export function endSpeaking(authToken: string, sessionId: number) {
  return invoke<Record<string, any>>("speaking_end", { authToken, session_id: sessionId });
}

// ── Pronunciation ──────────────────────────────────────────────────────────

export type PronunciationMode = "word" | "sentence" | "daily" | "minimal_pairs";

export interface PronunciationItemPayload {
  item_id: string;
  practice_mode: string;
  content: { title?: string; practice_text?: string; practice_lines?: string[] };
  text?: string;
}

export function startPronunciationSession(authToken: string, practiceMode: PronunciationMode, difficulty: Difficulty) {
  return invoke<{ session_id: number; item: PronunciationItemPayload; total_questions: number }>(
    "pronunciation_session_start",
    { authToken, practice_mode: practiceMode, difficulty },
  );
}

export function startPronunciationAttempt(authToken: string, itemId: string) {
  return invoke<{ data: { attempt_id: string } }>("pronunciation_start_attempt", { authToken, item_id: itemId });
}

export function submitPronunciation(
  authToken: string,
  opts: { itemId: string; attemptId: string; sessionId: number; recognisedText: string },
) {
  return invoke<Record<string, any>>("pronunciation_submit", {
    authToken,
    item_id: opts.itemId,
    attempt_id: opts.attemptId,
    session_id: opts.sessionId,
    recognised_text: opts.recognisedText,
  });
}

export function endPronunciationSession(authToken: string, sessionId: number) {
  return invoke<Record<string, any>>("pronunciation_session_end", { authToken, session_id: sessionId });
}
