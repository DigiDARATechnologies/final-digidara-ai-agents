import type { ChatOption, User } from "../types";
import {
  bridgeIdentity,
  endPronunciationSession,
  endSpeaking,
  endWriting,
  getDailyChallengeToday,
  getDashboard,
  getHistory,
  respondSpeaking,
  respondWriting,
  startPronunciationAttempt,
  startPronunciationSession,
  startSpeaking,
  startWriting,
  submitPronunciation,
  type Difficulty,
  type PronunciationItemPayload,
  type PronunciationMode,
} from "./communicationApi";

export type CommunicationStep =
  | "main_menu"
  | "awaiting_writing_topic"
  | "awaiting_speaking_topic"
  | "awaiting_pronunciation_mode"
  | "writing_turn"
  | "speaking_turn"
  | "pronunciation_turn";

export interface CommunicationFlowState {
  step: CommunicationStep;
  authToken?: string;
  userName?: string;
  difficulty: Difficulty;
  sessionId?: number;
  turnNumber?: number;
  totalTurns?: number;
  promptText?: string;
  pronunciationMode?: PronunciationMode;
  currentItemId?: string;
  currentItemText?: string;
  currentAttemptId?: string;
  activeModule?: "writing" | "speaking" | "pronunciation";
  lastScores?: Record<string, number | null>;
  lastFeedback?: string;
}

export interface CommunicationFlowMessage {
  text: string;
  options?: ChatOption[];
}

export const MENU_OPTIONS: ChatOption[] = [
  { label: "🗣️ Speaking Practice", value: "speaking" },
  { label: "✍️ Writing Practice", value: "writing" },
  { label: "🔤 Pronunciation Practice", value: "pronunciation" },
];

const DIFFICULTY_OPTIONS: ChatOption[] = [
  { label: "Easy", value: "easy" },
  { label: "Medium", value: "medium" },
  { label: "Hard", value: "hard" },
];

const PRONUNCIATION_MODE_OPTIONS: ChatOption[] = [
  { label: "Word", value: "word", description: "Practice pronouncing a single word" },
  { label: "Sentence", value: "sentence", description: "Practice pronouncing a full sentence" },
  { label: "Minimal pairs", value: "minimal_pairs", description: "Tell two similar-sounding words apart" },
];

function baseState(): CommunicationFlowState {
  return { step: "main_menu", difficulty: "medium" };
}

function menuMessage(intro: string): CommunicationFlowMessage {
  return { text: intro, options: MENU_OPTIONS };
}

function scoreLine(label: string, value: number | null | undefined): string {
  return value === null || value === undefined ? `${label}: —` : `${label}: ${value}/10`;
}

function formatScores(scores: Record<string, unknown> | null | undefined): string {
  if (!scores) return "";
  return Object.entries(scores)
    .filter(([key, value]) => key !== "overall" && value !== null && value !== undefined)
    .map(([key, value]) => scoreLine(key[0].toUpperCase() + key.slice(1), value as number | null))
    .concat(scores.overall === null || scores.overall === undefined ? [] : scoreLine("Overall", scores.overall as number | null))
    .join(" · ");
}

function itemText(item: PronunciationItemPayload): string {
  if (item.content?.practice_lines?.length) return item.content.practice_lines.join("\n");
  return item.content?.practice_text || item.content?.title || item.text || "Practice item";
}

export async function openCommunicationChat(
  user: User,
): Promise<{ state: CommunicationFlowState; messages: CommunicationFlowMessage[] }> {
  const base = baseState();
  try {
    const { authToken, user: bridgedUser } = await bridgeIdentity(user.name, user.email);
    return {
      state: { ...base, authToken, userName: bridgedUser.name },
      messages: [menuMessage(`Hi ${bridgedUser.name.split(" ")[0]}! What would you like to practice today?`)],
    };
  } catch (error) {
    return {
      state: base,
      messages: [{ text: `I could not connect to the Communication Coach: ${(error as Error).message}`, options: [{ label: "Try again", value: "retry" }] }],
    };
  }
}

async function showMenu(state: CommunicationFlowState, intro: string) {
  return { state: { ...state, step: "main_menu" as const }, messages: [menuMessage(intro)] };
}

async function showDashboard(state: CommunicationFlowState) {
  try {
    const d = await getDashboard(state.authToken!);
    const lines = [
      `Sessions completed: ${d.sessions_completed}`,
      `Overall score: ${d.overall_score ?? "—"}/10`,
      `Speaking: ${d.speaking_average ?? "—"}/10 (${d.speaking_completed} sessions)`,
      `Writing: ${d.writing_average ?? "—"}/10 (${d.writing_completed} sessions)`,
      `Pronunciation: ${d.pronunciation_average ?? "—"}/10 (${d.pronunciation_completed} sessions)`,
      `Best skill: ${d.best_skill?.label ?? "—"}`,
      `Needs work: ${d.needs_work?.label ?? "—"}`,
    ];
    return showMenu(state, lines.join("\n"));
  } catch (error) {
    return showMenu(state, `Could not load your progress: ${(error as Error).message}`);
  }
}

async function showHistory(state: CommunicationFlowState) {
  try {
    const { items } = await getHistory(state.authToken!);
    if (!items.length) return showMenu(state, "No practice history yet — finish a session and it will show up here.");
    const lines = items
      .slice(0, 8)
      .map((item) => `${item.type ?? "session"} — ${item.topic_title ?? "Practice"} — score ${item.overall_score ?? "—"}/10`);
    return showMenu(state, `Recent activity:\n${lines.join("\n")}`);
  } catch (error) {
    return showMenu(state, `Could not load your history: ${(error as Error).message}`);
  }
}

async function showDailyChallenge(state: CommunicationFlowState) {
  try {
    const status = await getDailyChallengeToday(state.authToken!);
    const activities = (status.activities as Array<Record<string, any>>) || [];
    const lines = activities.map((a) => `${a.completed ? "✅" : "⬜"} ${a.title} (+${a.xp_reward} XP)`);
    return {
      state: { ...state, step: "main_menu" as const },
      messages: [{
        text: `Today's Communication Challenge (${status.completed_count}/${status.total_count} completed):\n${lines.join("\n")}\n\nChoose a pending activity to start it.`,
        options: activities.filter((a) => !a.completed).map((a) => ({
          label: a.title,
          value: `daily_${a.module}`,
          description: `${a.status === "in_progress" ? "Continue" : "Start"} · +${a.xp_reward} XP`,
        })),
      }],
    };
  } catch (error) {
    return showMenu(state, `Could not load today's challenge: ${(error as Error).message}`);
  }
}

async function beginPronunciationSession(
  state: CommunicationFlowState,
  mode: PronunciationMode,
): Promise<{ state: CommunicationFlowState; messages: CommunicationFlowMessage[] }> {
  try {
    const { session_id, item } = await startPronunciationSession(state.authToken!, mode, state.difficulty);
    const { data } = await startPronunciationAttempt(state.authToken!, item.item_id);
    return {
      state: {
        ...state,
        step: "pronunciation_turn",
        activeModule: "pronunciation",
        sessionId: session_id,
        pronunciationMode: mode,
        currentItemId: item.item_id,
        currentItemText: itemText(item),
        currentAttemptId: data.attempt_id,
        lastScores: undefined,
        lastFeedback: undefined,
      },
      messages: [{
        text: `Read this out loud, then type what you said:\n\n"${itemText(item)}"`,
        options: [{ label: "End session", value: "end_session" }],
      }],
    };
  } catch (error) {
    return showMenu(state, `Could not start pronunciation practice: ${(error as Error).message}`);
  }
}

async function beginDailyWriting(state: CommunicationFlowState) {
  try {
    const result = await startWriting(state.authToken!, { mode: "daily", difficulty: state.difficulty });
    return { state: { ...state, step: "writing_turn" as const, activeModule: "writing" as const, sessionId: result.session_id, turnNumber: result.turn_number, totalTurns: result.total_turns }, messages: [{ text: result.prompt || "Write your response below.", options: [{ label: "End session", value: "end_session" }] }] };
  } catch (error) { return showMenu(state, `Could not start daily writing: ${(error as Error).message}`); }
}

async function beginDailySpeaking(state: CommunicationFlowState) {
  try {
    const result = await startSpeaking(state.authToken!, { mode: "daily", difficulty: state.difficulty });
    const question = result.turns?.[0]?.ai_question || result.question;
    return { state: { ...state, step: "speaking_turn" as const, activeModule: "speaking" as const, sessionId: result.session_id ?? result.id }, messages: [{ text: question || "Tell me about it.", options: [{ label: "End session", value: "end_session" }] }] };
  } catch (error) { return showMenu(state, `Could not start daily speaking: ${(error as Error).message}`); }
}

async function beginSpeakingPractice(state: CommunicationFlowState, difficulty: Difficulty) {
  const topics: Record<Difficulty, { title: string; description: string }> = {
    easy: { title: "Everyday Conversation", description: "Talk about your day, interests, routines, and familiar experiences." },
    medium: { title: "Ideas and Experiences", description: "Explain an experience, share an opinion, and support it with clear details." },
    hard: { title: "Professional Discussion", description: "Discuss a professional issue, analyze alternatives, and justify your position." },
  };
  try {
    const topic = topics[difficulty];
    const result = await startSpeaking(state.authToken!, { mode: "topic", difficulty, topicTitle: topic.title, topicDescription: topic.description });
    const question = result.turns?.[0]?.ai_question || result.question;
    return { state: { ...state, difficulty, step: "speaking_turn" as const, activeModule: "speaking" as const, sessionId: result.session_id ?? result.id, lastScores: undefined, lastFeedback: undefined }, messages: [{ text: question || "Tell me about your day.", options: [{ label: "End session", value: "end_session" }] }] };
  } catch (error) {
    return showMenu(state, `Could not start speaking practice: ${(error as Error).message}`);
  }
}

export async function handleCommunicationText(
  state: CommunicationFlowState,
  text: string,
): Promise<{ state: CommunicationFlowState; messages: CommunicationFlowMessage[] }> {
  const trimmed = text.trim();
  const command = trimmed.toLowerCase();

  if (command === "menu" || command === "back_to_menu") return showMenu(state, "What would you like to practice next?");

  if (state.step === "main_menu") {
    if (command === "dashboard") return showDashboard(state);
    if (command === "history") return showHistory(state);
    if (command === "daily_challenge") return showDailyChallenge(state);
    if (command === "daily_writing") return beginDailyWriting(state);
    if (command === "daily_speaking") return beginDailySpeaking(state);
    if (command === "daily_pronunciation") return beginPronunciationSession(state, "daily");
    if (command === "writing") {
      return {
        state: { ...state, step: "awaiting_writing_topic" },
        messages: [{
          text: "What would you like to write about? Type a topic, or 'daily' for today's Daily Writing Challenge.",
          options: DIFFICULTY_OPTIONS,
        }],
      };
    }
    if (command === "speaking") {
      return {
        state: { ...state, step: "awaiting_speaking_topic" },
        messages: [{
          text: "What would you like to talk about? Type a topic, or 'daily' for today's Daily Conversation.",
          options: DIFFICULTY_OPTIONS,
        }],
      };
    }
    if (command === "pronunciation") {
      return {
        state: { ...state, step: "awaiting_pronunciation_mode" },
        messages: [{ text: "Choose a pronunciation practice mode:", options: PRONUNCIATION_MODE_OPTIONS }],
      };
    }
    return showMenu(state, "Pick an option below to get started.");
  }

  if (state.step === "awaiting_writing_topic") {
    if (["easy", "medium", "hard"].includes(command)) {
      return { state: { ...state, difficulty: command as Difficulty }, messages: [{ text: `Difficulty set to ${command}. What topic would you like to write about?` }] };
    }
    try {
      const isDaily = command === "daily";
      const result = await startWriting(state.authToken!, {
        mode: isDaily ? "daily" : "topic",
        difficulty: state.difficulty,
        topicTitle: isDaily ? undefined : trimmed.slice(0, 120),
        topicDescription: isDaily ? undefined : `Write about: ${trimmed}`.slice(0, 500),
      });
      return {
        state: {
          ...state,
          step: "writing_turn",
          activeModule: "writing",
          sessionId: result.session_id,
          turnNumber: result.turn_number,
          totalTurns: result.total_turns,
          lastScores: undefined,
          lastFeedback: undefined,
        },
        messages: [{ text: result.prompt || "Write your response below.", options: [{ label: "End session", value: "end_session" }] }],
      };
    } catch (error) {
      return { state, messages: [{ text: `Could not start writing practice: ${(error as Error).message}` }] };
    }
  }

  if (state.step === "awaiting_speaking_topic") {
    if (["easy", "medium", "hard"].includes(command)) {
      return beginSpeakingPractice(state, command as Difficulty);
    }
    try {
      const isDaily = command === "daily";
      const result = await startSpeaking(state.authToken!, {
        mode: isDaily ? "daily" : "topic",
        difficulty: state.difficulty,
        topicTitle: isDaily ? undefined : trimmed.slice(0, 120),
        topicDescription: isDaily ? undefined : `Talk about: ${trimmed}`.slice(0, 500),
      });
      const question = result.turns?.[0]?.ai_question || result.question;
      return {
        state: { ...state, step: "speaking_turn", activeModule: "speaking", sessionId: result.session_id ?? result.id, lastScores: undefined, lastFeedback: undefined },
        messages: [{ text: question || "Tell me about it.", options: [{ label: "End session", value: "end_session" }] }],
      };
    } catch (error) {
      return { state, messages: [{ text: `Could not start speaking practice: ${(error as Error).message}` }] };
    }
  }

  if (state.step === "awaiting_pronunciation_mode") {
    const mode = ["word", "sentence", "minimal_pairs"].includes(command) ? (command as PronunciationMode) : undefined;
    if (!mode) return { state, messages: [{ text: "Pick a mode from the list.", options: PRONUNCIATION_MODE_OPTIONS }] };
    return beginPronunciationSession(state, mode);
  }

  if (state.step === "writing_turn") {
    if (command === "end_session") {
      try {
        const summary = await endWriting(state.authToken!, state.sessionId!);
        return showMenu(
          state,
          `Session complete! Overall score: ${summary.overall_score ?? "—"}/10\n${summary.summary_feedback ?? summary.summary ?? ""}`,
        );
      } catch (error) {
        return showMenu(state, `Could not end the session: ${(error as Error).message}`);
      }
    }
    try {
      const result = await respondWriting(state.authToken!, state.sessionId!, trimmed);
      const feedback = result.feedback;
      const lines = [
        feedback?.short_feedback || feedback?.feedback || "Got it.",
        formatScores(feedback?.scores),
        feedback?.corrected_answer ? `Corrected: ${feedback.corrected_answer}` : "",
        "",
        result.prompt || "",
      ].filter(Boolean);
      return {
        state: {
          ...state,
          turnNumber: result.turn_number,
          totalTurns: result.total_turns,
          lastScores: feedback?.scores,
          lastFeedback: feedback?.short_feedback || feedback?.feedback,
        },
        messages: [{ text: lines.join("\n"), options: [{ label: "End session", value: "end_session" }] }],
      };
    } catch (error) {
      return { state, messages: [{ text: `Could not save your answer: ${(error as Error).message}` }] };
    }
  }

  if (state.step === "speaking_turn") {
    if (command === "end_session") {
      try {
        const result = await endSpeaking(state.authToken!, state.sessionId!);
        const summary = result.summary || {};
        return showMenu(
          state,
          `Session complete! Overall score: ${summary.overall_score ?? "—"}/10\n${summary.summary_feedback ?? ""}`,
        );
      } catch (error) {
        return showMenu(state, `Could not end the session: ${(error as Error).message}`);
      }
    }
    try {
      const result = await respondSpeaking(state.authToken!, state.sessionId!, trimmed);
      if (result.done) {
        const summary = result.summary || {};
        return showMenu(
          state,
          `Session complete! Overall score: ${summary.overall_score ?? "—"}/10\n${summary.summary_feedback ?? ""}`,
        );
      }
      const nextQuestion = result.next_question || "Tell me more.";
      return {
        state: {
          ...state,
          turnNumber: result.turn_number,
          totalTurns: result.total_turns,
          lastScores: result.feedback?.scores,
          lastFeedback: result.feedback?.explanation,
        },
        messages: [{ text: nextQuestion, options: [{ label: "End session", value: "end_session" }] }],
      };
    } catch (error) {
      return { state, messages: [{ text: `Could not save your answer: ${(error as Error).message}` }] };
    }
  }

  if (state.step === "pronunciation_turn") {
    if (command === "end_session") {
      try {
        const summary = await endPronunciationSession(state.authToken!, state.sessionId!);
        return showMenu(
          state,
          `Session complete! Average score: ${summary.average_score ?? summary.overall_score ?? "—"}/10\n${summary.summary_feedback ?? ""}`,
        );
      } catch (error) {
        return showMenu(state, `Could not end the session: ${(error as Error).message}`);
      }
    }
    try {
      const result = await submitPronunciation(state.authToken!, {
        itemId: state.currentItemId!,
        attemptId: state.currentAttemptId!,
        sessionId: state.sessionId!,
        recognisedText: trimmed,
      });
      const turnScores = result.last_turn_result?.scores || result.scores;
      const lines = [formatScores(turnScores)];
      const nextItem: PronunciationItemPayload | undefined = result.next_item;
      if (nextItem) {
        const { data } = await startPronunciationAttempt(state.authToken!, nextItem.item_id);
        lines.push("", `Next: "${itemText(nextItem)}"`);
        return {
          state: {
            ...state,
            currentItemId: nextItem.item_id,
            currentItemText: itemText(nextItem),
            currentAttemptId: data.attempt_id,
            lastScores: turnScores,
          },
          messages: [{ text: lines.join("\n"), options: [{ label: "End session", value: "end_session" }] }],
        };
      }
      return showMenu(state, lines.join("\n") || "Nice work!");
    } catch (error) {
      return { state, messages: [{ text: `Could not score your attempt: ${(error as Error).message}` }] };
    }
  }

  return showMenu(state, "What would you like to practice?");
}
