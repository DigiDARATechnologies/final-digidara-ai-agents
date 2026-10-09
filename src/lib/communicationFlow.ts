import type { ChatOption, User } from "../types";
import {
  bridgeIdentity,
  downloadSpeakingReportPdf,
  downloadWritingReportPdf,
  finishWritingChat,
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
  writingChat,
  submitPronunciation,
  type Difficulty,
  type PronunciationItemPayload,
  type PronunciationMode,
  type SpeakingTurnResult,
  type WritingTurnResult,
} from "./communicationApi";
import { displayRole, easyMediumHard, learnerGoal } from "./learnerContext";

export type CommunicationStep =
  | "main_menu"
  | "awaiting_writing_topic"
  | "awaiting_writing_mode"
  | "awaiting_speaking_topic"
  | "awaiting_pronunciation_mode"
  | "writing_turn"
  | "writing_result"
  | "writing_chat_turn"
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
  /** The first captured word while completing a minimal-pair item. */
  minimalPairResponses?: string[];
  activeModule?: "writing" | "speaking" | "pronunciation";
  writingMode?: "write" | "chat";
  writingTopic?: string;
  writingTopicDescription?: string;
  writingChatHistory?: Array<{ role: "assistant" | "user"; text: string }>;
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

function greetingFor(name?: string): string {
  const hour = new Date().getHours();
  const period = hour >= 5 && hour < 12 ? "morning" : hour < 17 ? "afternoon" : hour < 21 ? "evening" : "night";
  const firstName = String(name || "").trim().split(/\s+/)[0];
  return firstName ? `Good ${period}, ${firstName}!` : `Good ${period}!`;
}

function openingSpeakingPrompt(state: CommunicationFlowState, question?: string): string {
  return [greetingFor(state.userName), question || "What did you do today?"].join(" ");
}

function normalizedSentence(value?: string): string {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function formatExecutiveScorecard(summary: Record<string, any>): string {
  const scorecard = summary.executive_scorecard || {};
  const scores = scorecard.scores_breakdown || {
    overall: Math.round(Number(summary.overall_score || 7.5) * 10),
    grammar: Math.round(Number(summary.grammar_score || 7.0) * 10),
    vocabulary: 76,
    clarity: Math.round(Number(summary.clarity_score || 7.2) * 10),
    sentence_structure: 68,
    fluency: Math.round(Number(summary.fluency_score || 7.4) * 10),
    confidence: Math.round(Number(summary.confidence_score || 7.6) * 10),
  };

  const youDidWell = scorecard.you_did_well || (summary.strengths?.[0] ? `Clearly expressed your thoughts on ${summary.topic_title || "the topic"}.` : "Communicated ideas actively.");
  const improve = scorecard.key_improvement_area || (summary.areas_to_improve?.[0] ? summary.areas_to_improve[0] : "Sentence structure and grammatical precision.");
  const rewrite = scorecard.golden_rewrite;
  const recommendation = summary.recommendation || scorecard.recommended_next_step || "10-minute workplace communication practice";

  let out = `🏆 **Communication Practice Complete**\n\n`;
  out += `📊 **Performance Scorecard:**\n`;
  out += `• **Overall:** ${scores.overall || 75}/100\n`;
  out += `• **Grammar:** ${scores.grammar || 70}/100\n`;
  out += `• **Vocabulary:** ${scores.vocabulary || 76}/100\n`;
  out += `• **Clarity:** ${scores.clarity || 72}/100\n`;
  out += `• **Sentence Structure:** ${scores.sentence_structure || 68}/100\n`;
  out += `• **Fluency:** ${scores.fluency || 74}/100\n`;
  out += `• **Confidence:** ${scores.confidence || 76}/100\n\n`;

  out += `✨ **You Did Well:**\n${youDidWell}\n\n`;
  out += `🎯 **Focus Area to Improve:**\n${improve}\n\n`;

  if (rewrite && rewrite.original && rewrite.better) {
    out += `💡 **Golden Rewrite (Executive Level):**\n`;
    out += `• *Original:* “${rewrite.original}”\n`;
    out += `• *Better:* “${rewrite.better}”\n\n`;
  }

  out += `🚀 **Recommended Next Step:**\n${recommendation}`;
  return out;
}

function deduplicateReaction(reaction: string, nextQuestion: string): string {
  let clean = reaction.trim();
  const normNext = normalizedSentence(nextQuestion);
  if (!normNext) return clean;

  const sentences = clean.match(/[^.!?]+[.!?]*/g) || [clean];
  const filtered = sentences.filter((s) => normalizedSentence(s) !== normNext);
  if (filtered.length > 0 && filtered.length < sentences.length) {
    clean = filtered.join(" ").trim();
  } else if (normalizedSentence(clean) === normNext) {
    clean = "";
  }
  return clean;
}

function speakingCoachReply(answer: string, feedback: SpeakingTurnResult["feedback"], nextQuestion: string): string {
  const rawReaction = String(feedback?.reaction || "You're doing well!").trim();
  const reaction = deduplicateReaction(rawReaction, nextQuestion);
  const corrected = String(feedback?.corrected_answer || "").trim();
  const hasCorrection = Boolean(corrected && normalizedSentence(corrected) !== normalizedSentence(answer));
  const correction = hasCorrection
    ? `Just a small correction. Instead of: “${answer}” You can say: “${corrected}”`
    : "";
  return [reaction, correction, nextQuestion].filter(Boolean).join(" ");
}

const DIFFICULTY_OPTIONS: ChatOption[] = [
  { label: "Easy", value: "easy" },
  { label: "Medium", value: "medium" },
  { label: "Hard", value: "hard" },
];

const WRITING_MODE_OPTIONS: ChatOption[] = [
  { label: "✍️ Write about the topic with AI", value: "writing_mode_write", description: "Answer a writing prompt in a paragraph" },
  { label: "💬 Chat with AI", value: "writing_mode_chat", description: "Have a guided conversation about your topic" },
];

const WRITING_WORD_TARGETS: Record<Difficulty, { range: string; target: number }> = {
  easy: { range: "80–100", target: 90 },
  medium: { range: "120–150", target: 135 },
  hard: { range: "180–200", target: 190 },
};

function writingExercisePrompt(question: string, difficulty: Difficulty): string {
  const target = WRITING_WORD_TARGETS[difficulty];
  return `${question}\n\nWriting instruction: Write a clear paragraph of about ${target.range} words. Explain your ideas clearly and use complete sentences.`;
}

const NO_CORRECTIONS = /no (?:major )?grammar corrections?/i;

/** Every correction the evaluator found, as "❌ wrong → ✅ right" lines with
 * the reason under each, then better word choices. Reads the structured
 * `mistakes` first and falls back to the `mistake_points` strings, so a
 * correction is never dropped because the evaluator used the other field. */
export function writingCorrections(feedback: NonNullable<WritingTurnResult["feedback"]>): string {
  const seen = new Set<string>();
  const lines: string[] = [];
  for (const item of feedback.mistakes || []) {
    const wrong = String(item.incorrect || "").trim();
    const right = String(item.correct || "").trim();
    if (!wrong || !right || normalizedSentence(wrong) === normalizedSentence(right) || seen.has(wrong.toLowerCase())) continue;
    seen.add(wrong.toLowerCase());
    const why = String(item.explanation || "").trim();
    lines.push(`• ❌ “${wrong}” → ✅ “${right}”${why ? `\n  ${why}` : ""}`);
  }
  if (!lines.length) {
    for (const point of feedback.mistake_points || []) {
      const text = String(point || "").trim();
      if (!text || NO_CORRECTIONS.test(text)) continue;
      lines.push(`• ${text.replace(/^["“]([^"”]+)["”]\s*(?:→|->)\s*["“]([^"”]+)["”]/, "❌ “$1” → ✅ “$2”")}`);
    }
  }
  const words = (feedback.vocabulary_suggestions || [])
    .filter((item) => item.original && item.suggestion && normalizedSentence(item.original) !== normalizedSentence(item.suggestion))
    .slice(0, 3)
    .map((item) => `• “${item.original}” → “${item.suggestion}”${item.example ? `\n  e.g. ${item.example}` : ""}`);
  return [
    lines.length ? `**Corrections (${lines.length}):**\n${lines.join("\n")}` : "**Corrections:** ✅ No grammar mistakes found.",
    words.length ? `**Better word choices:**\n${words.join("\n")}` : "",
  ].filter(Boolean).join("\n\n");
}

function writingEvaluationResult(feedback: NonNullable<WritingTurnResult["feedback"]>): string {
  const scores = feedback.scores || {};
  const score = (label: string, key: string) => `${label}: ${scores[key] == null ? "—" : scores[key]}/10`;
  return [
    "Focus on grammar and clarity for improvement.",
    [score("Clarity", "clarity"), score("Grammar", "grammar"), score("Knowledge", "knowledge"), score("Spelling", "spelling"), score("Vocabulary", "vocabulary"), score("Overall", "overall")].join(" · "),
    writingCorrections(feedback),
    `**Corrected paragraph:**\n“${feedback.corrected_answer || feedback.better_natural_answer || "Your paragraph was received."}”`,
  ].join("\n\n");
}

function writingChatReply(reply: string, originalAnswer?: string, correctedAnswer?: string | null, reaction?: string, nextQuestion?: string): string {
  const original = String(originalAnswer || "").trim();
  const corrected = String(correctedAnswer || "").trim();
  const hasCorrection = Boolean(corrected && original && normalizedSentence(corrected) !== normalizedSentence(original));
  const correction = hasCorrection ? `Just a small correction: Instead of “${original}”, you can say: “${corrected}”` : "";
  return [reaction, correction, nextQuestion].filter(Boolean).join("\n\n") || reply;
}

const PRONUNCIATION_MODE_OPTIONS: ChatOption[] = [
  { label: "Word", value: "word", description: "Practice pronouncing a single word" },
  { label: "Sentence", value: "sentence", description: "Practice pronouncing a full sentence" },

];

function baseState(): CommunicationFlowState {
  // The learner's Communication level (Beginner -> easy ... Professional -> hard).
  return { step: "main_menu", difficulty: easyMediumHard("communication_agent") };
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

function minimalPairWords(itemTextValue?: string): string[] {
  const parts = String(itemTextValue || "").split(/\s*\/\s*/);
  if (parts.length !== 2) return [];
  return parts.map((part) => {
    const words = part.match(/[a-z]+(?:'[a-z]+)?/gi) || [];
    return (words.at(-1) || "").toLowerCase();
  }).filter(Boolean);
}

function minimalPairPrompt(words: string[], capturedCount: number): string {
  const nextWord = words[capturedCount] || "the next word";
  return `Captured word ${capturedCount} of 2. Click the microphone again and pronounce “${nextWord}”, then press Send to receive your score.`;
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
        minimalPairResponses: undefined,
        lastScores: undefined,
        lastFeedback: undefined,
      },
      messages: [{
        text: mode === "minimal_pairs"
          ? `Pronunciation activity\n\n1. Click the microphone button below to turn it on.\n2. Say the first word in the pair: “${itemText(item)}”.\n3. Press Send, then record the second word when prompted. You will receive one score for both words.`
          : `Pronunciation activity\n\n1. Click the microphone button below to turn it on.\n2. Pronounce this clearly: “${itemText(item)}”\n3. Check the captured text, then press Send for scoring.`,
        options: [{ label: "End session", value: "end_session" }],
      }],
    };
  } catch (error) {
    return showMenu(state, `Could not start pronunciation practice: ${(error as Error).message}`);
  }
}

async function beginDailyWriting(state: CommunicationFlowState): Promise<{ state: CommunicationFlowState; messages: CommunicationFlowMessage[] }> {
  try {
    const result = await startWriting(state.authToken!, { mode: "daily", difficulty: state.difficulty });
    return { state: { ...state, step: "writing_turn" as const, activeModule: "writing" as const, sessionId: result.session_id, turnNumber: result.turn_number, totalTurns: result.total_turns }, messages: [{ text: result.prompt || "Write your response below.", options: [{ label: "End session", value: "end_session" }] }] };
  } catch (error) { return showMenu(state, `Could not start daily writing: ${(error as Error).message}`); }
}

async function beginWritingMode(state: CommunicationFlowState, writingMode: "write" | "chat"): Promise<{ state: CommunicationFlowState; messages: CommunicationFlowMessage[] }> {
  const topic = state.writingTopic;
  if (!topic) return showMenu(state, "Please enter a writing topic first.");

  if (writingMode === "chat") {
    try {
      const result = await writingChat(state.authToken!, topic, state.difficulty, []);
      const reply = writingChatReply(result.reply || `That's an interesting topic! What do you already know about ${topic}?`, undefined, result.corrected_answer, result.reaction, result.next_question);
      return {
        state: { ...state, step: "writing_chat_turn", activeModule: "writing", writingMode, writingChatHistory: [{ role: "assistant", text: reply }] },
        messages: [{ text: reply, options: [{ label: "End session", value: "end_session" }] }],
      };
    } catch (error) {
      return { state, messages: [{ text: `Could not start the writing chat: ${(error as Error).message}`, options: WRITING_MODE_OPTIONS }] };
    }
  }

  try {
    const result = await startWriting(state.authToken!, {
      mode: "topic",
      difficulty: state.difficulty,
      topicTitle: topic,
      topicDescription: state.writingTopicDescription || `Write about: ${topic}`,
    });
    return {
      state: { ...state, step: "writing_turn", activeModule: "writing", writingMode, sessionId: result.session_id, turnNumber: result.turn_number, totalTurns: result.total_turns, lastScores: undefined, lastFeedback: undefined },
      messages: [{ text: writingExercisePrompt(result.prompt || "Write your paragraph about this topic.", state.difficulty), options: [{ label: "End session", value: "end_session" }] }],
    };
  } catch (error) {
    return { state, messages: [{ text: `Could not generate a writing prompt: ${(error as Error).message}`, options: WRITING_MODE_OPTIONS }] };
  }
}

async function beginDailySpeaking(state: CommunicationFlowState) {
  try {
    const result = await startSpeaking(state.authToken!, { mode: "daily", difficulty: state.difficulty });
    const question = result.turns?.[0]?.ai_question || result.question;
    return { state: { ...state, step: "speaking_turn" as const, activeModule: "speaking" as const, sessionId: result.session_id ?? result.id }, messages: [{ text: openingSpeakingPrompt(state, question), options: [{ label: "End session", value: "end_session" }] }] };
  } catch (error) { return showMenu(state, `Could not start daily speaking: ${(error as Error).message}`); }
}

async function beginSpeakingPractice(state: CommunicationFlowState, difficulty: Difficulty) {
  const topics: Record<Difficulty, { title: string; description: string }> = {
    easy: { title: "Everyday Conversation", description: "Talk about your day, interests, routines, and familiar experiences." },
    medium: { title: "Ideas and Experiences", description: "Explain an experience, share an opinion, and support it with clear details." },
    hard: { title: "Professional Discussion", description: "Discuss a professional issue, analyze alternatives, and justify your position." },
  };
  // With a target role, practise speaking for that job instead of generic topics.
  const goal = learnerGoal();
  if (goal) {
    const role = displayRole(goal.targetRole);
    const skills = goal.skills.slice(0, 3).join(", ") || "your skills";
    topics.easy = { title: `Introduce Yourself as an Aspiring ${role}`,
      description: `Introduce yourself for a ${role} role: your studies${goal.degree ? ` (${goal.degree})` : ""}, your skills (${skills}) and why this job excites you.` };
    topics.medium = { title: `Explain a ${role} Project`,
      description: `Explain a project or idea that uses ${skills}, clearly enough for a ${role} interviewer to follow.` };
    topics.hard = { title: `${role} Interview Discussion`,
      description: `Discuss a real ${role} challenge, compare approaches and justify your choice as you would in a job interview.` };
  }
  try {
    const topic = topics[difficulty];
    const result = await startSpeaking(state.authToken!, { mode: "topic", difficulty, topicTitle: topic.title, topicDescription: topic.description });
    const question = result.turns?.[0]?.ai_question || result.question;
    return { state: { ...state, difficulty, step: "speaking_turn" as const, activeModule: "speaking" as const, sessionId: result.session_id ?? result.id, lastScores: undefined, lastFeedback: undefined }, messages: [{ text: openingSpeakingPrompt(state, question), options: [{ label: "End session", value: "end_session" }] }] };
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

  if (command === "download_speaking_pdf") {
    if (!state.sessionId || !state.authToken) {
      return showMenu(state, "No completed speaking session found to download.");
    }
    try {
      await downloadSpeakingReportPdf(state.authToken, state.sessionId);
      return {
        state: { ...state, step: "main_menu" as const },
        messages: [{
          text: "Your Speaking Practice Report PDF has been downloaded successfully! 📄✨\n\nWhat would you like to practice next?",
          options: MENU_OPTIONS,
        }],
      };
    } catch (error) {
      return {
        state: { ...state, step: "main_menu" as const },
        messages: [{
          text: `Could not download the report PDF: ${(error as Error).message}`,
          options: [
            { label: "📄 Try Download PDF Again", value: "download_speaking_pdf" },
            ...MENU_OPTIONS,
          ],
        }],
      };
    }
  }

  if (command === "download_writing_pdf") {
    if (!state.sessionId || !state.authToken) {
      return showMenu(state, "No completed writing session found to download.");
    }
    try {
      await downloadWritingReportPdf(state.authToken, state.sessionId);
      return {
        state: { ...state, step: "main_menu" as const },
        messages: [{
          text: "Your Writing Practice Report PDF has been downloaded successfully! 📄✨\n\nWhat would you like to practice next?",
          options: MENU_OPTIONS,
        }],
      };
    } catch (error) {
      return {
        state: { ...state, step: "main_menu" as const },
        messages: [{
          text: `Could not download the writing report PDF: ${(error as Error).message}`,
          options: [
            { label: "📄 Try Download PDF Again", value: "download_writing_pdf" },
            ...MENU_OPTIONS,
          ],
        }],
      };
    }
  }

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
    if (command === "daily") return beginDailyWriting(state);
    if (trimmed.length < 3) return { state, messages: [{ text: "Please enter a topic with at least 3 characters." }] };
    return {
      state: { ...state, step: "awaiting_writing_mode", writingTopic: trimmed.slice(0, 120), writingTopicDescription: `Write about: ${trimmed}`.slice(0, 500), writingMode: undefined },
      messages: [{ text: "How would you like to practise this topic?", options: WRITING_MODE_OPTIONS }],
    };
  }

  if (state.step === "awaiting_writing_mode") {
    if (command === "writing_mode_write") return beginWritingMode(state, "write");
    if (command === "writing_mode_chat") return beginWritingMode(state, "chat");
    return { state, messages: [{ text: "Choose Write about the topic with AI or Chat with AI.", options: WRITING_MODE_OPTIONS }] };
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
        messages: [{ text: openingSpeakingPrompt(state, question), options: [{ label: "End session", value: "end_session" }] }],
      };
    } catch (error) {
      return { state, messages: [{ text: `Could not start speaking practice: ${(error as Error).message}` }] };
    }
  }

  if (state.step === "awaiting_pronunciation_mode") {
    const mode = ["word", "sentence"].includes(command) ? (command as PronunciationMode) : undefined;
    if (!mode) return { state, messages: [{ text: "Pick a mode from the list.", options: PRONUNCIATION_MODE_OPTIONS }] };
    return beginPronunciationSession(state, mode);
  }

  if (state.step === "writing_turn") {
    if (command === "end_session") {
      try {
        const summary = await endWriting(state.authToken!, state.sessionId!);
        const scoreText = summary.overall_score !== null && summary.overall_score !== undefined
          ? `${summary.overall_score}/10`
          : "—/10";
        return {
          state: { ...state, step: "main_menu" as const },
          messages: [{
            text: `Writing practice complete! Overall score: ${scoreText}\n${summary.summary_feedback ?? summary.summary ?? ""}\n\nYour Writing Practice Report PDF is ready:`,
            options: [
              { label: "📄 Download PDF Report", value: "download_writing_pdf", description: "Download your detailed writing analysis PDF" },
              ...MENU_OPTIONS,
            ],
          }],
        };
      } catch (error) {
        return showMenu(state, `Could not end the session: ${(error as Error).message}`);
      }
    }
    try {
      const isWriteMode = state.writingMode === "write";
      const result = await respondWriting(state.authToken!, state.sessionId!, trimmed, isWriteMode);
      const feedback = result.feedback;
      if (isWriteMode) {
        return {
          state: { ...state, step: "writing_result", lastScores: feedback?.scores, lastFeedback: feedback?.short_feedback || feedback?.feedback },
          messages: [{ text: writingEvaluationResult(feedback || {}), options: [{ label: "End session", value: "end_session" }] }],
        };
      }
      const corrected = String(feedback?.corrected_answer || "").trim();
      const lines = [
        feedback?.short_feedback || feedback?.feedback || "Got it.",
        formatScores(feedback?.scores),
        feedback ? writingCorrections(feedback) : "",
        corrected && normalizedSentence(corrected) !== normalizedSentence(trimmed) ? `**Corrected answer:**\n“${corrected}”` : "",
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
        messages: [{ text: lines.join("\n\n"), options: [{ label: "End session", value: "end_session" }] }],
      };
    } catch (error) {
      return { state, messages: [{ text: `Could not save your answer: ${(error as Error).message}` }] };
    }
  }

  if (state.step === "writing_result") {
    if (command === "end_session") {
      try {
        const summary = await endWriting(state.authToken!, state.sessionId!);
        const scoreText = summary.overall_score !== null && summary.overall_score !== undefined
          ? `${summary.overall_score}/10`
          : "—/10";
        return {
          state: { ...state, step: "main_menu" as const },
          messages: [{
            text: `Writing practice complete! Overall score: ${scoreText}\n${summary.summary_feedback ?? summary.summary ?? ""}\n\nYour Writing Practice Report PDF is ready:`,
            options: [
              { label: "📄 Download PDF Report", value: "download_writing_pdf", description: "Download your detailed writing analysis PDF" },
              ...MENU_OPTIONS,
            ],
          }],
        };
      } catch (error) {
        return showMenu(state, `Could not end the session: ${(error as Error).message}`);
      }
    }
    return { state, messages: [{ text: "Your writing evaluation is complete. Choose End session when you are ready.", options: [{ label: "End session", value: "end_session" }] }] };
  }

  if (state.step === "writing_chat_turn") {
    if (command === "end_session") {
      // The AI's messages are "reaction\n\ncorrection\n\nnext question"; the
      // report shows each answer under the question it replied to.
      const history = (state.writingChatHistory || []).map((entry) => (
        entry.role === "assistant" ? { ...entry, text: entry.text.split("\n\n").pop() || entry.text } : entry
      ));
      if (!history.some((entry) => entry.role === "user")) {
        return showMenu(state, "Writing chat ended. What would you like to practise next?");
      }
      try {
        const summary = await finishWritingChat(state.authToken!, state.writingTopic || "this topic", state.difficulty, history);
        const scoreText = summary.overall_score !== null && summary.overall_score !== undefined ? `${summary.overall_score}/10` : "—/10";
        return {
          state: { ...state, step: "main_menu" as const, sessionId: summary.session_id, writingChatHistory: undefined },
          messages: [{
            text: `Writing chat complete! Overall score: ${scoreText}\n${summary.summary_feedback ?? ""}\n\nYour Writing Practice Report PDF is ready, with every correction from this chat:`,
            options: [
              { label: "📄 Download PDF Report", value: "download_writing_pdf", description: "Download your detailed writing analysis PDF" },
              ...MENU_OPTIONS,
            ],
          }],
        };
      } catch (error) {
        return showMenu(state, `Writing chat ended, but the report could not be prepared: ${(error as Error).message}`);
      }
    }
    try {
      const history = [...(state.writingChatHistory || []), { role: "user" as const, text: trimmed }];
      const result = await writingChat(state.authToken!, state.writingTopic || "this topic", state.difficulty, history);
      const reply = writingChatReply(result.reply || "That's a good start! Could you tell me a little more?", trimmed, result.corrected_answer, result.reaction, result.next_question);
      return {
        state: { ...state, writingChatHistory: [...history, { role: "assistant", text: reply }] },
        messages: [{ text: reply, options: [{ label: "End session", value: "end_session" }] }],
      };
    } catch (error) {
      return { state, messages: [{ text: `Could not continue the writing chat: ${(error as Error).message}` }] };
    }
  }

  if (state.step === "speaking_turn") {
    if (command === "end_session") {
      try {
        const result = await endSpeaking(state.authToken!, state.sessionId!);
        const summary = result.summary || {};
        const scorecard = formatExecutiveScorecard(summary);
        return {
          state: { ...state, step: "main_menu" as const },
          messages: [{
            text: `${scorecard}\n\nYour Speaking Practice Report PDF is ready:`,
            options: [
              { label: "🚀 Start Recommended Practice", value: "speaking", description: "Start your recommended next session" },
              { label: "📄 Download PDF Report", value: "download_speaking_pdf", description: "Download your detailed speaking analysis PDF" },
              ...MENU_OPTIONS,
            ],
          }],
        };
      } catch (error) {
        return showMenu(state, `Could not end the session: ${(error as Error).message}`);
      }
    }
    try {
      const result = await respondSpeaking(state.authToken!, state.sessionId!, trimmed);
      if (result.done) {
        const summary = result.summary || {};
        const scorecard = formatExecutiveScorecard(summary);
        const farewell = String(result.message || result.feedback?.reaction || "").trim();
        const farewellPrefix = farewell ? `${farewell}\n\n` : "";
        return {
          state: { ...state, step: "main_menu" as const },
          messages: [{
            text: `${farewellPrefix}${scorecard}\n\nYour Speaking Practice Report PDF is ready:`,
            options: [
              { label: "🚀 Start Recommended Practice", value: "speaking", description: "Start your recommended next session" },
              { label: "📄 Download PDF Report", value: "download_speaking_pdf", description: "Download your detailed speaking analysis PDF" },
              ...MENU_OPTIONS,
            ],
          }],
        };
      }
      const nextQuestion = result.next_question || "Tell me more.";
      const coachReply = speakingCoachReply(trimmed, result.feedback, nextQuestion);
      return {
        state: {
          ...state,
          turnNumber: result.turn_number,
          totalTurns: result.total_turns,
          lastScores: result.feedback?.scores,
          lastFeedback: result.feedback?.explanation,
        },
        messages: [{ text: coachReply, options: [{ label: "End session", value: "end_session" }] }],
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
      const pairWords = minimalPairWords(state.currentItemText);
      const previousPairResponses = state.pronunciationMode === "minimal_pairs"
        ? state.minimalPairResponses || []
        : [];
      const pairResponses = state.pronunciationMode === "minimal_pairs"
        ? [...previousPairResponses, trimmed]
        : [];

      // Minimal-pair scoring evaluates each word separately. Retain the
      // first short utterance instead of sending it as an incomplete pair.
      if (state.pronunciationMode === "minimal_pairs" && pairResponses.length < 2) {
        return {
          state: { ...state, minimalPairResponses: pairResponses },
          messages: [{ text: minimalPairPrompt(pairWords, pairResponses.length), options: [{ label: "End session", value: "end_session" }] }],
        };
      }
      const result = await submitPronunciation(state.authToken!, {
        itemId: state.currentItemId!,
        attemptId: state.currentAttemptId!,
        sessionId: state.sessionId!,
        recognisedText: trimmed,
        minimalPairResponses: pairResponses.length
          ? pairResponses.map((recognised_text) => ({ recognised_text }))
          : undefined,
      });
      const turnScores = result.last_turn_result?.scores || result.scores;
      const lines = [formatScores(turnScores)];
      const nextItem: PronunciationItemPayload | undefined = result.next_item;
      if (nextItem) {
        const { data } = await startPronunciationAttempt(state.authToken!, nextItem.item_id);
        lines.push("", `Next pronunciation activity:\n1. Click the microphone button below.\n2. Pronounce clearly: “${itemText(nextItem)}”\n3. Check the captured text, then press Send for scoring.`);
        return {
          state: {
            ...state,
            currentItemId: nextItem.item_id,
            currentItemText: itemText(nextItem),
            currentAttemptId: data.attempt_id,
            minimalPairResponses: undefined,
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
