import { CAPSTONE_EXAMPLE_OPTIONS } from "./capstoneExamples";
import type { ChatOption, User } from "../types";
import {
  askProjectQuestion,
  checkEligibilityFree,
  chooseTopic,
  confirmTimer,
  downloadFinalReport,
  getThreadStatus,
  startVivaAttempt,
  submitVivaAnswer,
  topicIntakeTurn,
  uploadSubmission,
  type CodeQualityScore,
  type IntakeMemory,
  type IntakeSlot,
  type IntakeTurn,
  type IntakeTurnResult,
  type ProjectDifficulty,
  type SyntaxErrorDetail,
  type TopicOption,
} from "./capstoneApi";

/** A rough, deliberately over-inclusive heuristic: is this message the
 * student asking something or disputing a finding, rather than a plain
 * answer/instruction-following action (a viva answer, or just re-attaching
 * files)? Covers two shapes seen in practice: a genuine question ("what
 * does X mean?"), and a dispute/objection ("already have the approach
 * section", "that's wrong", "no I did include that"). False positives (a
 * genuine answer misread as one of these) just cost one extra turn where
 * the student re-sends their answer — cheap. False negatives (a real
 * question/dispute silently consumed as a literal viva answer, or dropped
 * with a canned reminder) are the actual bug this exists to prevent, so
 * this errs toward catching more, not fewer. */
function looksLikeQuestionOrDispute(text: string): boolean {
  const trimmed = text.trim();
  if (/\?\s*$/.test(trimmed)) return true;
  return /^(hey|hi|hello|wait|excuse me|sorry|actually|no[,]?\s|already|i (already )?(have|wrote|did|add(ed)?|includ(e|ed)|do have)|that'?s (wrong|not right|incorrect)|this is (already|not)|i don'?t (think|agree)|question|quick question|one (question|sec|moment)|i have (a|one) question|i want(ed)? to ask|can i ask|could i ask)\b/i.test(trimmed);
}

/** Every step from awaiting_topic_choice onward has a real thread_id (a
 * project/assignment already exists), so a doubt there can be routed through
 * askProjectQuestion for a real, grounded answer. At awaiting_topic_request
 * there is nothing yet to ask about -- the thread only gets created by the
 * first topic-generation call -- so there's no equivalent agent to consult.
 * This narrowly catches plain small talk / meta questions ("hi", "who is
 * the pm", "how are you") that are clearly not a topic request, so they get
 * a short explanation of what this chat does instead of being fed into
 * clarifyTopicRequest as if they were one. Deliberately narrow: a real
 * request that happens to end in "?" (e.g. "can I get a python project?")
 * must NOT match this, so it can't reuse the broad looksLikeQuestionOrDispute
 * heuristic above. */
const OFF_TOPIC_SMALL_TALK = /^(hi|hello+|hey|yo|thanks|thank you|ok(ay)?|who (is|are|was)|what('s| is) your name|how are you|how('s| is) it going|good (morning|afternoon|evening))\b/i;

/** Once a project's requirements are shown it is locked in: a request to
 * change the language, topic or project gets a plain answer saying so,
 * instead of going to the Q&A agent. */
const LOCKED_CHANGE_REQUEST = /\bregenerate\b|\b(change|switch|update|replace|swap)\b[^.?!]*\b(project|topic|title|language|option|idea)s?\b|\b(different|another|other|new)\s+(two\s+)?(project|topic|title|language|option|idea)s?\b/i;

/** Why a project question could not be answered, in words the student can act on. */
function qaFailureText(error: unknown): string {
  const message = (error as Error)?.message ?? "";
  const reason = /timed out|timeout|504/i.test(message)
    ? "the answer took too long to prepare"
    : message
      ? `the project assistant returned an error (${message})`
      : "the project assistant could not be reached";
  return `I couldn't answer your question just now because ${reason}. Nothing is lost — please send it again.`;
}

/** The chat option that downloads the final report PDF. */
export const FINAL_REPORT_ACTION = "download_final_report";

/** The chat option that opens the certificate preview (name check, OK, download). */
export const CERTIFICATE_ACTION = "open_certificate";

/** The chat option that begins the next viva attempt after a failed one. */
export const START_VIVA_ACTION = "start_viva_attempt";

function finalReportOptions(): ChatOption[] {
  return [{
    label: "Download final report (PDF)",
    value: FINAL_REPORT_ACTION,
    description: "Your score, viva results and project details, with the DigiDARA Technologies logo on every page.",
  }];
}

function certificateOptions(): ChatOption[] {
  return [{
    label: "Get my certificate",
    value: CERTIFICATE_ACTION,
    description: "Preview it, check your name, click OK, and download the PDF.",
  }];
}

/** Everything a student who passed can take away, certificate first. */
function passOptions(): ChatOption[] {
  return [...certificateOptions(), ...finalReportOptions()];
}

const VIVA_PASS_PERCENT = 50;

function vivaRetryOptions(nextAttempt: number, total: number): ChatOption[] {
  return [{
    label: `Start viva attempt ${nextAttempt} of ${total}`,
    value: START_VIVA_ACTION,
    description: "A fresh set of questions — none repeated from your earlier attempt.",
  }];
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

export type CapstoneStep =
  | "awaiting_topic_request"
  | "awaiting_topic_choice"
  | "awaiting_timer_confirm"
  | "awaiting_submission"
  | "awaiting_viva_answer"
  | "graded";

export interface CapstoneFlowMessage {
  text: string;
  options?: ChatOption[];
}

export interface CapstoneFlowState {
  step: CapstoneStep;
  name: string;
  email: string;
  phone: string;
  /** Chosen via the connector pill. Defaults to "easy". Changing it while
   * still on awaiting_topic_request just updates the pending level; changing
   * it on awaiting_topic_choice re-generates the topic options at the new
   * level (see regenerateTopicsForDifficulty). Fixed once a topic is chosen. */
  difficulty: ProjectDifficulty;
  /** Chats saved before the intake memory existed: the first answer, held
   * while a clarifying question was pending. Read once into `intake`. */
  pendingTopicSeed?: string;
  /** The request as shown back to the student ("Java — Web development"). */
  topicSeed?: string;
  /** What the student has told us before a project is locked in — the
   * language/role, the type of project, extra details. Every field stays
   * editable ("change the language to java") until a project is chosen. */
  intake?: IntakeMemory;
  /** Which intake field the last question asked for. */
  pendingQuestion?: IntakeSlot;
  /** The last intake question, repeated after answering a side question. */
  pendingQuestionText?: string;
  /** The recent intake conversation, sent with every turn so the agent can
   * resolve "that one" or "change it back". */
  intakeHistory?: IntakeTurn[];
  /** Every topic title shown in this chat, so "other topics" never repeats one. */
  shownTopicTitles?: string[];
  threadId?: string;
  topicOptions?: TopicOption[];
  chosenTopic?: TopicOption;
  requirements?: Record<string, any>;
  deadlineAt?: string;
  submissionGuide?: Record<string, any>;
  finalScore?: number | null;
  passed?: boolean | null;
  feedback?: string | null;
  revisionNotes?: string | null;
  /** The final-score aggregator's own 2-3 sentence explanation of how it
   * weighed the four reviewers' scores — separate from `feedback`, which is
   * the learner-facing prose message. */
  scoreReasoning?: string | null;
  /** Per-axis code review breakdown (structure/syntax/maintainability/
   * completeness + strengths/weaknesses) behind the single `finalScore`
   * number — already computed by CodeQualityScorerNode, just not previously
   * surfaced past the chat's summary text. */
  codeQualityScore?: CodeQualityScore | null;
  docxFile?: File;
  zipFile?: File;
  /** An image the student attached to ask about; read by the agent with their next message. */
  imageFile?: File;
  /** Post-grading viva (oral defense) — see app/viva.py on the backend. */
  vivaSubmissionId?: string | null;
  vivaQuestionId?: number | null;
  vivaQuestionText?: string | null;
  vivaProgress?: string | null;
  vivaScore?: number | null;
  vivaPassed?: boolean | null;
  /** The viva result as a word (Good / Average / Bad) -- never shown as a mark. */
  vivaRating?: string | null;
  vivaAttempt?: number | null;
  vivaAttemptsTotal?: number | null;
  /** A viva attempt just failed and another is available: waiting for the student
   * to start it (there is no pending question until they do). */
  vivaRetryPending?: boolean;
}

export interface CapstoneFlowResult {
  state: CapstoneFlowState;
  messages: CapstoneFlowMessage[];
  /** One-shot request for the chat to open the dashboard (the certificate preview lives there). */
  openDashboard?: boolean;
}

export function createInitialCapstoneState(user: User): CapstoneFlowState {
  return {
    step: "awaiting_topic_request",
    name: user.name,
    email: user.email,
    phone: user.mobile,
    difficulty: "easy",
    pendingQuestion: "focus",
  };
}

const FOCUS_QUESTION = 'What language, role, or topic would you like your capstone project to be based on? (e.g. "Python", "Data Analyst", "e-commerce website")';

function projectTypeQuestion(focus: string): string {
  return `What type of project or application would you like to build with ${focus}? (e.g. web app, desktop tool, REST API, data analysis — or say "your choice")`;
}

export function initialCapstoneMessage(user: User): CapstoneFlowMessage {
  return { text: `Hi ${user.name.split(" ")[0]}! ${FOCUS_QUESTION}` };
}

function formatRequirements(req: Record<string, any>): string {
  const lines: string[] = [];
  if (req.objective) lines.push(req.objective);
  if (req.functional_requirements?.length) {
    lines.push("\nFunctional requirements:");
    req.functional_requirements.forEach((item: string) => lines.push(`- ${item}`));
  }
  if (req.technical_constraints?.length) {
    lines.push("\nTechnical constraints:");
    req.technical_constraints.forEach((item: string) => lines.push(`- ${item}`));
  }
  if (req.expected_deliverables?.length) lines.push(`\nDeliverables: ${req.expected_deliverables.join(", ")}`);
  if (req.estimated_effort_hours) lines.push(`Estimated effort: about ${req.estimated_effort_hours} hours`);
  return lines.join("\n");
}

function formatSubmissionGuide(guide: Record<string, any>, deadlineAt: string): string {
  const lines: string[] = [`Your 7-day timer has started. Deadline: ${new Date(deadlineAt).toLocaleString()}`];
  if (guide.docx_required_sections?.length) lines.push(`\nRequired report sections: ${guide.docx_required_sections.join(" -> ")}`);
  if (guide.folder_structure?.length) lines.push(`\nZip folder structure:\n${guide.folder_structure.map((line: string) => `  ${line}`).join("\n")}`);
  if (guide.required_screenshots?.length) {
    lines.push("\nOutput screenshots - save each as its own image file in the output_screenshots folder of your zip (not in the .docx report):");
    guide.required_screenshots.forEach((item: { filename?: string; module?: string; description?: string }, index: number) => {
      const module = item.module ? `${item.module}: ` : "";
      lines.push(`${index + 1}. ${item.filename ?? "screenshot.png"} - ${module}${item.description ?? ""}`);
    });
    lines.push("Ask me about any screenshot and I will explain exactly what it must show and how to capture it.");
  }
  if (guide.common_mistakes?.length) {
    lines.push("\nCommon mistakes to avoid:");
    guide.common_mistakes.forEach((item: string) => lines.push(`- ${item}`));
  }
  return lines.join("\n");
}

const HISTORY_LIMIT = 12;
const SHOWN_TITLES_LIMIT = 60;
const ANY_PROJECT_TYPE = /^(any|anything|your choice)$/i;

/** The intake memory, including for chats saved before it existed. */
function intakeOf(state: CapstoneFlowState): IntakeMemory {
  if (state.intake) return state.intake;
  if (state.topicSeed) return { focus: state.topicSeed, project_type: "Any" };
  if (state.pendingTopicSeed) return { focus: state.pendingTopicSeed };
  return {};
}

function rememberTurns(state: CapstoneFlowState, studentText: string, messages: CapstoneFlowMessage[]): CapstoneFlowState {
  const turns: IntakeTurn[] = [
    ...(state.intakeHistory ?? []),
    { role: "student", text: studentText },
    ...messages.map((message) => ({ role: "agent" as const, text: message.text })),
  ];
  return { ...state, intakeHistory: turns.slice(-HISTORY_LIMIT) };
}

function topicChoiceOptions(topics: TopicOption[] | undefined): ChatOption[] | undefined {
  return topics?.map((topic) => ({ label: `${topic.id}. ${topic.title}`, value: topic.id, description: topic.summary }));
}

/** "your choice", "idk", "anything" -- leaves the project type open. */
const DEFERRAL_ANSWER = /^(your|you'?re|any|the)?\s*(choice|pick|call|decision)$|^you\s*(decide|choose|pick)$|^(any|anything|up to you|surprise me|whatever|no preference|idk|not sure|doesn'?t matter)$/i;

/** Words that make a message more than a plain answer: an edit, a request
 * for other topics, a difficulty change, or a question. */
const NOT_A_PLAIN_ANSWER = /\?|\b(change|update|switch|instead|actually|not|no|regenerate|another|other|different|new|more|harder|easier|easy|medium|hard|difficulty|what|why|how|which|can|could|should|explain|help|hi|hello|hey)\b/i;

/** A short reply ("Python", "Login page", "your choice") answering the
 * pending question -- taken as the answer directly, without a model call. */
function isPlainAnswer(text: string): boolean {
  if (DEFERRAL_ANSWER.test(text)) return true;
  return text.split(/\s+/).length <= 4 && text.length <= 40 && !NOT_A_PLAIN_ANSWER.test(text);
}

const LANGUAGE_NAME = /^(python|java|javascript|js|typescript|ts|c|c\+\+|cpp|c#|csharp|go|golang|rust|kotlin|swift|php|ruby|r|dart|scala|html|css|html\s*(and|&|\/)?\s*css|sql|react|angular|vue|node(\.?js)?|django|flask|spring|flutter|\.net|dotnet)$/i;

/** "I need another two topics", "regenerate", "show me other ideas", "change the topics". */
const PLAIN_REGENERATE = /^(please\s+)?(i\s+(need|want)\s+(to\s+)?|give\s+me\s+|show\s+me\s+|can\s+i\s+(get|have)\s+)?(a\s+)?(regenerate(\s+(the\s+)?(topics?|ideas?|options?|projects?))?|(an?\s*other|other|new|different|more)\s+(two\s+)?(topics?|ideas?|options?|projects?)|change\s+(the\s+)?(project\s+)?(topics?|ideas?|options?))(\s+please)?[.!]?$/i;

const CHOOSE_PROMPT = 'Choose project A or B to continue — or tell me what to change (the language, the type of project, or "show me other topics").';

/** What goes to the topic generator for this memory: `description` for the
 * LLM, `label` for the chat, `key` for the shared past-topics pool. */
function generationRequest(memory: IntakeMemory): { description: string; label: string; key: string } {
  const focus = memory.focus ?? "";
  const type = memory.project_type ?? "";
  const openType = !type || ANY_PROJECT_TYPE.test(type.trim());
  const label = openType ? focus : `${focus} — ${type}`;
  let description = label;
  if (memory.details) description += ` (${memory.details})`;
  if (openType) description += " (the student left the type of project open — use your own best judgment)";
  const key = `${focus}|${openType ? "any" : type}`.toLowerCase().replace(/\s+/g, " ").trim();
  return { description, label, key };
}

/** Generates (or re-generates) two options from the intake memory, never
 * repeating a title this chat has already shown. */
async function generateTopicsFor(
  state: CapstoneFlowState,
  memory: IntakeMemory,
  lead?: string | null,
): Promise<{ state: CapstoneFlowState; messages: CapstoneFlowMessage[] }> {
  const { description, label, key } = generationRequest(memory);
  const seen = state.shownTopicTitles ?? [];
  try {
    const result = await checkEligibilityFree(state.name, state.email, state.phone, description, state.difficulty, {
      excludeTitles: seen,
      topicKey: key,
    });
    const topics = result.topic_options ?? [];
    const intro = seen.length ? `Here are two new ${state.difficulty} project options` : `I generated two ${state.difficulty} project options`;
    return {
      state: {
        ...state,
        intake: memory,
        pendingQuestion: undefined,
        pendingQuestionText: undefined,
        pendingTopicSeed: undefined,
        topicSeed: label,
        threadId: result.thread_id,
        topicOptions: topics,
        shownTopicTitles: [...seen, ...topics.map((topic) => topic.title)].slice(-SHOWN_TITLES_LIMIT),
        step: "awaiting_topic_choice",
      },
      messages: [{
        text: `${lead ? `${lead}\n\n` : ""}${intro} for "${label}". ${CHOOSE_PROMPT}`,
        options: topicChoiceOptions(topics),
      }],
    };
  } catch (error) {
    return {
      state: { ...state, intake: memory },
      messages: [{ text: `I could not generate a project for that: ${(error as Error).message}. Please try again.` }],
    };
  }
}

/** Asks for a missing intake field. Any options on screen are dropped — the
 * request they were generated for no longer holds. */
function askFor(
  state: CapstoneFlowState,
  memory: IntakeMemory,
  slot: IntakeSlot,
  question: string,
  lead?: string | null,
): { state: CapstoneFlowState; messages: CapstoneFlowMessage[] } {
  return {
    state: {
      ...state,
      intake: memory,
      step: "awaiting_topic_request",
      pendingQuestion: slot,
      pendingQuestionText: question,
      pendingTopicSeed: undefined,
      topicOptions: undefined,
      threadId: undefined,
    },
    messages: [{ text: lead ? `${lead}\n\n${question}` : question }],
  };
}

/** Moves on from the memory: ask for what's still missing, or generate. */
function continueIntake(
  state: CapstoneFlowState,
  memory: IntakeMemory,
  ready: boolean,
  nextQuestion?: string | null,
  lead?: string | null,
) {
  if (!memory.focus) return Promise.resolve(askFor(state, memory, "focus", nextQuestion || FOCUS_QUESTION, lead));
  if (!ready || !memory.project_type) {
    return Promise.resolve(askFor(state, memory, "project_type", nextQuestion || projectTypeQuestion(memory.focus), lead));
  }
  return generateTopicsFor(state, memory, lead);
}

async function lockTopic(state: CapstoneFlowState, topic: TopicOption): Promise<CapstoneFlowResult> {
  try {
    const result = await chooseTopic(state.threadId!, topic.id);
    return {
      state: { ...state, chosenTopic: topic, requirements: result.requirements, step: "awaiting_timer_confirm" },
      messages: [{
        text: `${formatRequirements(result.requirements)}\n\nNot sure how your report and zip should look? Download the examples below. Start the 7-day project timer when you are ready.`,
        options: [{ label: "Start 7-day timer", value: "confirm" }, ...CAPSTONE_EXAMPLE_OPTIONS],
      }],
    };
  } catch (error) {
    return { state, messages: [{ text: `I could not lock that project: ${(error as Error).message}` }] };
  }
}

function sameMemory(a: IntakeMemory, b: IntakeMemory): boolean {
  return (a.focus ?? null) === (b.focus ?? null)
    && (a.project_type ?? null) === (b.project_type ?? null)
    && (a.details ?? null) === (b.details ?? null)
    && (a.difficulty ?? null) === (b.difficulty ?? null);
}

/** The intake agent is unreachable: fall back to treating the message as the
 * answer to whatever was asked, or — with options on screen — as a question
 * for the project Q&A agent, which is how this chat worked before. */
async function intakeFallback(state: CapstoneFlowState, memory: IntakeMemory, text: string): Promise<CapstoneFlowResult> {
  const options = topicChoiceOptions(state.topicOptions);
  if (state.step === "awaiting_topic_choice") {
    if (state.threadId) {
      try {
        const qa = await askProjectQuestion(state.threadId, text);
        return { state, messages: [{ text: qa.answer }, { text: CHOOSE_PROMPT, options }] };
      } catch {
        // Q&A itself failed -- fall through to the plain reminder below.
      }
    }
    return { state, messages: [{ text: "Choose project A or B.", options }] };
  }
  if (!memory.focus || state.pendingQuestion === "focus") {
    const next = { ...memory, focus: text };
    return askFor(state, next, "project_type", projectTypeQuestion(text));
  }
  return generateTopicsFor(state, { ...memory, project_type: text });
}

/** Everything before a project is locked in: answering the two intake
 * questions, editing an earlier answer, asking for other topics, side
 * questions, and picking A or B. */
async function handleTopicIntake(state: CapstoneFlowState, text: string): Promise<CapstoneFlowResult> {
  const memory = intakeOf(state);
  const shownTopics = state.step === "awaiting_topic_choice" ? state.topicOptions ?? [] : [];

  // An exact selection ("A", "b", "option A", "A.") never needs the model.
  // Only an exact one: stripping any text down to a letter it happens to
  // contain silently picked a project for "I need to change the project topics".
  const exact = text.match(/^(?:option\s*)?([ab])\.?$/i);
  const exactTopic = exact ? shownTopics.find((topic) => topic.id === exact[1].toUpperCase()) : undefined;
  if (exactTopic) return lockTopic(state, exactTopic);

  if (!memory.focus && text.split(/\s+/).length <= 5 && OFF_TOPIC_SMALL_TALK.test(text)) {
    return {
      state,
      messages: [{
        text: 'I\'m the Capstone Project Agent — I help you choose a project topic, write out its requirements, track your 7-day build, and grade the final submission (with a short viva). Tell me the language, role, or topic you\'d like your project based on (e.g. "python", "data analyst", "e-commerce website") and I\'ll generate two options.',
      }],
    };
  }

  // Fast paths that need no model call (each one is a full LLM round-trip
  // the student waits on): a plain answer to the pending question, and a
  // plain "other topics" request.
  if (shownTopics.length && PLAIN_REGENERATE.test(text)) {
    const result = await generateTopicsFor(state, memory, "Sure — here are some different ideas.");
    return { ...result, state: rememberTurns(result.state, text, result.messages) };
  }
  // A bare language name while the project-type question is pending is most
  // likely a change of language ("java"), so that one still goes to the model.
  const languageSwitch = state.pendingQuestion === "project_type" && LANGUAGE_NAME.test(text);
  if (state.step === "awaiting_topic_request" && isPlainAnswer(text) && !languageSwitch) {
    const value = text.charAt(0).toUpperCase() + text.slice(1);
    const result = !memory.focus || state.pendingQuestion === "focus"
      ? askFor(state, { ...memory, focus: value }, "project_type", projectTypeQuestion(value))
      : await generateTopicsFor(state, { ...memory, project_type: DEFERRAL_ANSWER.test(text) ? "Any" : value });
    return { ...result, state: rememberTurns(result.state, text, result.messages) };
  }

  let turn: IntakeTurnResult;
  try {
    turn = await topicIntakeTurn({
      message: text,
      memory,
      pending_question: state.step === "awaiting_topic_request" ? state.pendingQuestion : undefined,
      shown_topics: shownTopics.map(({ id, title, summary }) => ({ id, title, summary })),
      history: state.intakeHistory ?? [],
    });
  } catch {
    return intakeFallback(state, memory, text);
  }

  let result: { state: CapstoneFlowState; messages: CapstoneFlowMessage[] };
  switch (turn.intent) {
    case "choose": {
      const topic = shownTopics.find((item) => item.id === turn.choice);
      if (topic) return lockTopic(state, topic);
      result = { state, messages: [{ text: CHOOSE_PROMPT, options: topicChoiceOptions(shownTopics) }] };
      break;
    }
    case "regenerate":
      result = await generateTopicsFor(state, memory, "Sure — here are some different ideas.");
      break;
    case "update": {
      const next: IntakeMemory = { ...turn.memory };
      const withLevel = next.difficulty && next.difficulty !== state.difficulty ? { ...state, difficulty: next.difficulty } : state;
      if (shownTopics.length && sameMemory(next, memory) && withLevel === state) {
        result = { state, messages: [{ text: turn.reply ? `${turn.reply}\n\n${CHOOSE_PROMPT}` : CHOOSE_PROMPT, options: topicChoiceOptions(shownTopics) }] };
        break;
      }
      result = await continueIntake(withLevel, next, turn.ready, turn.next_question, turn.reply);
      break;
    }
    default: {
      // A side question or small talk: answer it, then put the pending step back in front of the student.
      const reply = turn.reply || "I'm here to help you pick your capstone project.";
      const back: CapstoneFlowMessage = shownTopics.length
        ? { text: CHOOSE_PROMPT, options: topicChoiceOptions(shownTopics) }
        : { text: state.pendingQuestionText || (memory.focus ? projectTypeQuestion(memory.focus) : FOCUS_QUESTION) };
      result = { state, messages: [{ text: reply }, back] };
    }
  }
  return { ...result, state: rememberTurns(result.state, text, result.messages) };
}

/** A chat saved before failed grades were made retryable can be sitting in
 * the terminal "graded" step with `passed === false`. That is never a real
 * end state (only a pass is), so reopen it for another upload. */
function reopenIfFailed(state: CapstoneFlowState): CapstoneFlowState {
  if (state.step === "graded" && state.passed === false) {
    return { ...state, step: "awaiting_submission", docxFile: undefined, zipFile: undefined };
  }
  return state;
}

const IMAGE_NAME = /\.(png|jpe?g|gif|webp|bmp)$/i;
const isImage = (file: File) => file.type.startsWith("image/") || IMAGE_NAME.test(file.name);

/** The files waiting to be sent, in the order the chips are shown. */
export function capstonePendingFiles(state: CapstoneFlowState | undefined): File[] {
  return state ? [state.docxFile, state.zipFile, state.imageFile].filter((file): file is File => !!file) : [];
}

const DEFAULT_IMAGE_QUESTION = "What does this image show, and how does it relate to my project? Explain it to me.";

export async function handleCapstoneText(
  state: CapstoneFlowState,
  text: string,
): Promise<CapstoneFlowResult> {
  const trimmed = text.trim();
  state = reopenIfFailed(state);

  // An attached image is a question about that image, at any step -- it is never a viva
  // answer or a topic request. The agent reads the image and answers from it.
  if (state.imageFile && state.threadId) {
    const cleared = { ...state, imageFile: undefined };
    try {
      const qa = await askProjectQuestion(state.threadId, trimmed || DEFAULT_IMAGE_QUESTION, state.imageFile);
      const messages: CapstoneFlowMessage[] = [{ text: qa.answer }];
      if (state.step === "awaiting_viva_answer" && !state.vivaRetryPending && state.vivaQuestionText) {
        messages.push({ text: `Back to the viva — Question ${state.vivaProgress}:\n\n${state.vivaQuestionText}` });
      }
      return { state: cleared, messages };
    } catch (error) {
      // Keep the image attached so the student can just send again.
      return { state, messages: [{ text: `I could not read that image: ${(error as Error).message}. It is still attached — send your question again, or remove it.` }] };
    }
  }

  switch (state.step) {
    case "awaiting_topic_request":
    case "awaiting_topic_choice": {
      if (!trimmed) {
        return state.step === "awaiting_topic_choice"
          ? { state, messages: [{ text: CHOOSE_PROMPT, options: topicChoiceOptions(state.topicOptions) }] }
          : { state, messages: [{ text: "Tell me the language, role, or topic you'd like your project based on." }] };
      }
      return handleTopicIntake(state, trimmed);
    }

    case "awaiting_timer_confirm": {
      // The project was locked in the moment its requirements were shown.
      if (LOCKED_CHANGE_REQUEST.test(trimmed)) {
        return {
          state,
          messages: [{
            text: `Your project "${state.chosenTopic?.title ?? "this project"}" is locked in — its requirements are fixed now, so the language, project type and topic can no longer be changed. To work on a different project, start a new chat. Ask me anything about these requirements, or start the 7-day timer when you're ready.`,
            options: [{ label: "Start 7-day timer", value: "confirm" }],
          }],
        };
      }
      if (!/^(confirm|yes|start)/i.test(trimmed)) {
        // The only valid action here is confirming the timer, so anything
        // else typed is by definition a doubt about the requirements just
        // shown -- e.g. "what does 'must run offline' mean?" -- not just
        // messages that happen to match the question/dispute heuristic
        // used elsewhere. Answer it before the student starts an
        // irreversible 7-day clock over a misunderstanding.
        if (state.threadId) {
          try {
            const qa = await askProjectQuestion(state.threadId, trimmed);
            return {
              state,
              messages: [
                { text: qa.answer },
                { text: "Start the 7-day project timer when you're ready.", options: [{ label: "Start 7-day timer", value: "confirm" }] },
              ],
            };
          } catch (error) {
            // Say that the answer failed, and why -- a canned "use the button"
            // here read as the agent ignoring the question.
            return { state, messages: [{ text: qaFailureText(error), options: [{ label: "Start 7-day timer", value: "confirm" }] }] };
          }
        }
        return { state, messages: [{ text: "Use the button when you are ready. The timer cannot be paused.", options: [{ label: "Start 7-day timer", value: "confirm" }] }] };
      }
      try {
        const result = await confirmTimer(state.threadId!);
        return {
          state: { ...state, deadlineAt: result.deadline_at, submissionGuide: result.submission_guide, step: "awaiting_submission" },
          messages: [{
            text: `${formatSubmissionGuide(result.submission_guide, result.deadline_at)}\n\nI will monitor your project here. Attach the .docx report and .zip source code in this chat when ready. The example report and example project below show the expected format.`,
            options: CAPSTONE_EXAMPLE_OPTIONS,
          }],
        };
      } catch (error) {
        return { state, messages: [{ text: `I could not start the timer: ${(error as Error).message}`, options: [{ label: "Try again", value: "confirm" }] }] };
      }
    }

    case "awaiting_viva_answer": {
      if (state.vivaRetryPending) {
        if (!state.vivaSubmissionId) {
          return { state, messages: [{ text: "I lost track of the viva session. Please resubmit your project." }] };
        }
        const total = state.vivaAttemptsTotal ?? 3;
        const nextAttempt = (state.vivaAttempt ?? 1) + 1;
        if (trimmed === START_VIVA_ACTION || /^(y(es)?|start|ok(ay)?|ready|next|continue|retry|go|begin)\b/i.test(trimmed)) {
          try {
            const result = await startVivaAttempt(state.vivaSubmissionId);
            if (result.viva_question) {
              return {
                state: {
                  ...state,
                  vivaRetryPending: false,
                  vivaQuestionId: result.viva_question.id,
                  vivaQuestionText: result.viva_question.question,
                  vivaProgress: result.viva_progress,
                  vivaAttempt: result.viva_attempt ?? nextAttempt,
                  vivaAttemptsTotal: result.viva_attempts_total ?? total,
                },
                messages: [{
                  text: `Viva attempt ${result.viva_attempt ?? nextAttempt} of ${result.viva_attempts_total ?? total} — a new set of questions.\n\nQuestion ${result.viva_progress}:\n\n${result.viva_question.question}`,
                }],
              };
            }
          } catch (error) {
            return {
              state,
              messages: [{ text: `I could not start the next attempt: ${(error as Error).message}`, options: vivaRetryOptions(nextAttempt, total) }],
            };
          }
        }
        // Anything else is a question about the project -- answer it, then offer the attempt again.
        let answer = "";
        if (state.threadId && trimmed) {
          try {
            answer = (await askProjectQuestion(state.threadId, trimmed)).answer;
          } catch {
            // Q&A itself failed -- just re-offer the next attempt.
          }
        }
        return {
          state,
          messages: [
            ...(answer ? [{ text: answer }] : []),
            { text: `Start viva attempt ${nextAttempt} of ${total} whenever you're ready.`, options: vivaRetryOptions(nextAttempt, total) },
          ],
        };
      }
      if (!trimmed) {
        return { state, messages: [{ text: "Please answer the question above before continuing." }] };
      }
      if (!state.vivaSubmissionId || state.vivaQuestionId == null) {
        return { state, messages: [{ text: "I lost track of the viva session. Please resubmit your project." }] };
      }
      if (state.threadId && looksLikeQuestionOrDispute(trimmed)) {
        try {
          const qa = await askProjectQuestion(state.threadId, trimmed);
          return {
            state,
            messages: [
              { text: qa.answer },
              { text: `Shall we continue the viva? Here's the question again —\n\nQuestion ${state.vivaProgress}:\n\n${state.vivaQuestionText}` },
            ],
          };
        } catch {
          // Q&A itself failed (e.g. thread expired) — fall through and treat
          // the text as a literal viva answer rather than silently dropping it.
        }
      }
      try {
        const result = await submitVivaAnswer(state.vivaSubmissionId, state.vivaQuestionId, trimmed);
        if (result.status === "pending_viva" && result.viva_question) {
          return {
            state: {
              ...state,
              vivaQuestionId: result.viva_question.id,
              vivaQuestionText: result.viva_question.question,
              vivaProgress: result.viva_progress,
            },
            messages: [{ text: `Question ${result.viva_progress}:\n\n${result.viva_question.question}` }],
          };
        }
        const rating = result.viva_rating ?? null;
        const total = result.viva_attempts_total ?? 3;
        // An attempt that did not pass, with attempts left: nothing is decided yet.
        // The student starts the next attempt (new questions) when they are ready.
        if (result.status === "viva_retry") {
          const attempt = result.viva_attempt ?? 1;
          const left = result.viva_attempts_left ?? 0;
          return {
            state: {
              ...state,
              vivaRetryPending: true,
              vivaQuestionId: null,
              vivaQuestionText: null,
              vivaProgress: null,
              vivaAttempt: attempt,
              vivaAttemptsTotal: total,
              vivaRating: rating,
              vivaPassed: false,
            },
            messages: [{
              text: `Viva attempt ${attempt} of ${total} finished. Result: ${rating ?? "-"}.\n\nYou need at least ${VIVA_PASS_PERCENT}% of the answers correct to pass, so this attempt did not pass. You have ${plural(left, "attempt")} left, and every attempt asks new questions. Review your project, then start the next attempt when you're ready.`,
              options: vivaRetryOptions(attempt + 1, total),
            }],
          };
        }
        // A failed grade (low code score, or the viva not passed in every attempt) is
        // not a dead end: the backend leaves the assignment at `needs_revision`, not
        // `graded`, and accepts unlimited resubmissions until one passes.
        // Moving to the terminal "graded" step here used to lock the student
        // out of uploading again, so a fail goes back to awaiting_submission.
        if (result.status === "needs_revision" || result.passed === false) {
          return {
            state: {
              ...state,
              step: "awaiting_submission",
              docxFile: undefined,
              zipFile: undefined,
              vivaSubmissionId: null,
              vivaQuestionId: null,
              vivaQuestionText: null,
              vivaProgress: null,
              vivaRetryPending: false,
              vivaAttempt: null,
              finalScore: result.final_score,
              passed: false,
              feedback: result.feedback,
              revisionNotes: result.feedback ?? null,
              scoreReasoning: result.score_reasoning ?? null,
              codeQualityScore: result.code_quality_score ?? null,
              vivaScore: result.viva_score ?? null,
              vivaPassed: result.viva_passed ?? null,
              vivaRating: rating,
            },
            messages: [{
              text: `Score: ${result.final_score ?? "-"}/100 - Viva: ${rating ?? "-"} - Not passed\n\n${result.feedback ?? ""}\n\nYou can improve your project and attach both your .docx report and .zip source archive again — there is no limit on resubmitting until you pass.`,
            }],
          };
        }
        return {
          state: {
            ...state,
            step: "graded",
            finalScore: result.final_score,
            passed: result.passed,
            feedback: result.feedback,
            scoreReasoning: result.score_reasoning ?? null,
            codeQualityScore: result.code_quality_score ?? null,
            vivaScore: result.viva_score ?? null,
            vivaPassed: result.viva_passed ?? null,
            vivaRating: rating,
            vivaRetryPending: false,
          },
          messages: [{
            text: `Score: ${result.final_score ?? "-"}/100 - Viva: ${rating ?? "-"} - You passed!\n\n${result.feedback ?? ""}\n\nYour project is complete: the code score and the viva are both passed. Your certificate and your final report are ready.`,
            options: passOptions(),
          }],
        };
      } catch (error) {
        return { state, messages: [{ text: `I could not record that answer: ${(error as Error).message}` }] };
      }
    }
    case "awaiting_submission": {
      // Plain text is never itself a valid action here -- attaching files is
      // the only real action, and always goes through mergeCapstoneFiles,
      // not this text handler -- so any text always gets a real answer from
      // the Q&A agent, the same way awaiting_timer_confirm already treats
      // any non-confirm text. Previously this was pre-filtered by a
      // question-shaped-text heuristic that missed genuine requests like "I
      // can't understand the requirements, explain more" (no "?", no
      // matched opening phrase) and silently sent the canned reminder
      // instead of an actual answer.
      if (state.threadId && trimmed) {
        try {
          const qa = await askProjectQuestion(state.threadId, trimmed);
          return { state, messages: [{ text: qa.answer }, { text: "Attach both your .docx report and .zip source archive using the paperclip button when you're ready to resubmit." }] };
        } catch (error) {
          return { state, messages: [{ text: qaFailureText(error) }, { text: "Attach both your .docx report and .zip source archive using the paperclip button." }] };
        }
      }
      return { state, messages: [{ text: "Attach both your .docx report and .zip source archive using the paperclip button." }] };
    }
    case "graded": {
      const canDownload = Boolean(state.passed && state.vivaSubmissionId);
      if (trimmed === CERTIFICATE_ACTION) {
        if (!canDownload) return { state, messages: [{ text: "The certificate is available once both your project score and the viva are passed." }] };
        return {
          state,
          openDashboard: true,
          messages: [{
            text: "Your certificate preview is open in the project dashboard on the right. Check that your name is spelled the way you want it printed — the name is the only thing you can change — then click OK to issue it. After that, the PDF is ready to download.",
            options: passOptions(),
          }],
        };
      }
      if (trimmed === FINAL_REPORT_ACTION) {
        if (!canDownload) return { state, messages: [{ text: "The final report is available once both your project score and the viva are passed." }] };
        try {
          await downloadFinalReport(state.vivaSubmissionId!);
          return { state, messages: [{ text: "Your final report has been downloaded. You can download it again any time from here or the dashboard.", options: passOptions() }] };
        } catch (error) {
          return { state, messages: [{ text: `I could not download the report: ${(error as Error).message}`, options: passOptions() }] };
        }
      }
      return {
        state,
        messages: [{
          text: "This project has already been graded. Open the dashboard to review the result.",
          options: canDownload ? passOptions() : undefined,
        }],
      };
    }
  }
}

/** Re-runs topic generation for a new difficulty level after topics were
 * already generated (connector pill level change on awaiting_topic_choice).
 * Before any options exist it only records the level; once a topic is
 * chosen the level is already baked into the locked requirements. */
export async function regenerateTopicsForDifficulty(
  state: CapstoneFlowState,
  difficulty: ProjectDifficulty,
): Promise<{ state: CapstoneFlowState; messages: CapstoneFlowMessage[] }> {
  const memory = intakeOf(state);
  if (state.step !== "awaiting_topic_choice" || !memory.focus) {
    return { state: { ...state, difficulty }, messages: [] };
  }
  const result = await generateTopicsFor({ ...state, difficulty }, { ...memory, difficulty }, `Switched to ${difficulty} difficulty.`);
  // A failed regeneration leaves the current options (and their level) as they were.
  if (result.state.step !== "awaiting_topic_choice" || result.state.threadId === state.threadId) {
    return { state, messages: [{ text: `I could not regenerate projects at ${difficulty} difficulty. ${result.messages[0]?.text ?? ""}`.trim() }] };
  }
  return result;
}

export function mergeCapstoneFiles(state: CapstoneFlowState, files: File[]): { state: CapstoneFlowState; messages: CapstoneFlowMessage[] } {
  state = reopenIfFailed(state);
  const images = files.filter(isImage);
  if (images.length) {
    if (!state.threadId) {
      return { state, messages: [{ text: "Choose a project first — then you can attach a screenshot or image and ask me about it." }] };
    }
    const withImage = { ...state, imageFile: images[images.length - 1] };
    const rest = files.filter((file) => !isImage(file));
    if (!rest.length) {
      return { state: withImage, messages: [{ text: "Image attached. Type your question about it and press send — I'll read the image and answer. (Send with no text and I'll explain what it shows.)" }] };
    }
    const merged = mergeCapstoneFiles(withImage, rest);
    return { state: merged.state, messages: [{ text: "Image attached — ask your question about it whenever you like." }, ...merged.messages] };
  }
  if (state.step !== "awaiting_submission") return { state, messages: [{ text: "File upload becomes available after your project timer starts." }] };
  let docxFile = state.docxFile;
  let zipFile = state.zipFile;
  for (const file of files) {
    const name = file.name.toLowerCase();
    if (name.endsWith(".docx")) docxFile = file;
    if (name.endsWith(".zip")) zipFile = file;
  }
  const missing = [!docxFile && ".docx report", !zipFile && ".zip source archive"].filter(Boolean);
  const text = missing.length ? `File received. Still needed: ${missing.join(" and ")}.` : "Both files received. I am validating and grading them now.";
  return { state: { ...state, docxFile, zipFile }, messages: [{ text }] };
}

/** One syntax error laid out the way a terminal prints it: the file and line,
 * the offending source line, a caret under the column, then the message. The
 * source line keeps its own indentation, so the caret lines up. */
export function formatSyntaxError(error: SyntaxErrorDetail): string {
  const lines = [`  File "${error.path}"${error.line ? `, line ${error.line}` : ""}`];
  if (error.source_line) {
    lines.push(`    ${error.source_line}`);
    if (error.column && error.column > 0) lines.push(`    ${" ".repeat(error.column - 1)}^`);
  }
  lines.push(`${error.language === "Python" ? "SyntaxError" : `${error.language} syntax error`}: ${error.message}`);
  return lines.join("\n");
}

/** The chat message for a submission that was stopped by syntax errors: a
 * heading and each error as a fenced terminal block -- deliberately NOT the
 * generic "Revision needed" wording, since the errors themselves are the whole
 * point. Any other problems found (report sections, folder layout) follow. */
export function formatSyntaxErrorMessage(errors: SyntaxErrorDetail[], otherNotes?: string | null): string {
  const heading = errors.length === 1 ? "### Syntax error in your code" : `### ${errors.length} syntax errors in your code`;
  const parts = [heading, ...errors.map((error) => "```\n" + formatSyntaxError(error) + "\n```")];
  if (otherNotes?.trim()) parts.push(otherNotes.trim());
  parts.push("Attach both files again once it is fixed.");
  return parts.join("\n\n");
}

export async function submitCapstoneFiles(state: CapstoneFlowState): Promise<{ state: CapstoneFlowState; messages: CapstoneFlowMessage[] }> {
  if (!state.docxFile || !state.zipFile || !state.threadId) return { state, messages: [] };
  try {
    const result = await uploadSubmission(state.threadId, state.docxFile, state.zipFile);
    if (result.status === "needs_revision") {
      const nextState = {
        ...state,
        docxFile: undefined,
        zipFile: undefined,
        revisionNotes: result.revision_notes,
        finalScore: result.final_score ?? null,
        passed: result.passed ?? null,
        scoreReasoning: result.score_reasoning ?? null,
        codeQualityScore: result.code_quality_score ?? null,
      };
      // The code itself does not parse: show each error, not a summary of them.
      if (result.syntax_errors?.length) {
        return { state: nextState, messages: [{ text: formatSyntaxErrorMessage(result.syntax_errors, result.revision_notes) }] };
      }
      // A packaging/structure rejection never reaches content scoring, so
      // final_score is absent there — a failed *content* grade carries one
      // and gets the fuller message with the score, since the student
      // already earned that feedback and gets a real resubmission attempt.
      if (result.final_score != null) {
        return {
          state: nextState,
          messages: [{
            text: `Score: ${result.final_score}/100 - Not passed\n\n${result.revision_notes ?? ""}\n\nFix the issues above and attach both files again.`,
          }],
        };
      }
      return {
        state: nextState,
        messages: [{ text: `Revision needed:\n${result.revision_notes ?? "Review the validation notes."}\n\nFix the issues and attach both files again.` }],
      };
    }
    if (result.status === "pending_viva" && result.viva_question) {
      return {
        state: {
          ...state,
          step: "awaiting_viva_answer",
          vivaSubmissionId: result.submission_id,
          vivaQuestionId: result.viva_question.id,
          vivaQuestionText: result.viva_question.question,
          vivaProgress: result.viva_progress,
          vivaRetryPending: false,
          vivaAttempt: result.viva_attempt ?? 1,
          vivaAttemptsTotal: result.viva_attempts_total ?? 3,
        },
        messages: [{
          text: `Your project passed content grading. Before your score is revealed, there is a short viva: attempt ${result.viva_attempt ?? 1} of ${result.viva_attempts_total ?? 3}. You need at least ${VIVA_PASS_PERCENT}% of the answers correct to pass; if you don't, you can try again with new questions (up to ${result.viva_attempts_total ?? 3} attempts).\n\nQuestion ${result.viva_progress}:\n\n${result.viva_question.question}`,
        }],
      };
    }

    if (result.passed === false) {
      return {
        state: {
          ...state,
          docxFile: undefined,
          zipFile: undefined,
          finalScore: result.final_score,
          passed: false,
          feedback: result.feedback,
          revisionNotes: result.feedback ?? null,
          scoreReasoning: result.score_reasoning ?? null,
          codeQualityScore: result.code_quality_score ?? null,
        },
        messages: [{
          text: `Score: ${result.final_score ?? "-"}/100 - Not passed\n\n${result.feedback ?? ""}\n\nYou can improve your project and attach both files again — there is no limit on resubmitting until you pass.`,
        }],
      };
    }

    return {
      state: {
        ...state,
        step: "graded",
        finalScore: result.final_score,
        passed: result.passed,
        feedback: result.feedback,
        revisionNotes: null,
        scoreReasoning: result.score_reasoning ?? null,
        codeQualityScore: result.code_quality_score ?? null,
        vivaScore: result.viva_score ?? null,
        vivaPassed: result.viva_passed ?? null,
      },
      messages: [{ text: `Score: ${result.final_score ?? "-"}/100 - ${result.passed ? "Passed" : "Not passed"}\n\n${result.feedback ?? ""}` }],
    };
  } catch (error) {
    const message = (error as Error).message;
    if (/already been graded/i.test(message) && state.threadId) {
      // The grading that produced this outcome ran in an earlier attempt
      // whose response the browser never received (e.g. a dropped connection
      // or a heartbeat blip) — the score itself lives on the backend thread,
      // so fetch it instead of leaving the dashboard blank.
      try {
        const status = await getThreadStatus(state.threadId);
        return {
          state: {
            ...state,
            step: "graded",
            docxFile: undefined,
            zipFile: undefined,
            revisionNotes: null,
            finalScore: status.final_score,
            passed: status.passed,
            feedback: status.feedback,
          },
          messages: [{
            text: `This project was already graded. Score: ${status.final_score ?? "-"}/100 - ${status.passed ? "Passed" : "Not passed"}\n\n${status.feedback ?? ""}\n\nStart a new chat to work on another capstone project.`,
          }],
        };
      } catch {
        return {
          state: { ...state, step: "graded", docxFile: undefined, zipFile: undefined, revisionNotes: null },
          messages: [{ text: `${message} Start a new chat to work on another capstone project.` }],
        };
      }
    }
    return { state, messages: [{ text: `Submission failed: ${message}. Re-attach the files to try again.` }] };
  }
}
