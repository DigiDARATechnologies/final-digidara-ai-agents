import type { ChatOption, User } from "../types";
import {
  checkEligibilityFree,
  chooseTopic,
  clarifyTopicRequest,
  confirmTimer,
  getThreadStatus,
  submitVivaAnswer,
  uploadSubmission,
  type CodeQualityScore,
  type ProjectDifficulty,
  type TopicOption,
} from "./capstoneApi";

export type CapstoneStep =
  | "awaiting_topic_request"
  | "awaiting_topic_choice"
  | "awaiting_timer_confirm"
  | "awaiting_submission"
  | "awaiting_viva_answer"
  | "not_eligible"
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
  /** Set while awaiting the student's answer to one clarifying question
   * (see clarifyTopicRequest) — holds the original free text so the next
   * message can be combined with it into one enriched description, rather
   * than replacing it. Cleared once that combined description is sent to
   * checkEligibilityFree — capped at one clarifying round, not a loop. */
  pendingTopicSeed?: string;
  topicSeed?: string;
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
  /** Post-grading viva (oral defense) — see app/viva.py on the backend. */
  vivaSubmissionId?: string | null;
  vivaQuestionId?: number | null;
  vivaQuestionText?: string | null;
  vivaProgress?: string | null;
  vivaScore?: number | null;
  vivaPassed?: boolean | null;
}

export function createInitialCapstoneState(user: User): CapstoneFlowState {
  return {
    step: "awaiting_topic_request",
    name: user.name,
    email: user.email,
    phone: user.mobile,
    difficulty: "easy",
  };
}

export function initialCapstoneMessage(user: User): CapstoneFlowMessage {
  return {
    text: `Hi ${user.name.split(" ")[0]}! What language, role, or topic would you like your capstone project to be based on? (e.g. "Python", "Data Analyst", "e-commerce website")`,
  };
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
  if (guide.common_mistakes?.length) {
    lines.push("\nCommon mistakes to avoid:");
    guide.common_mistakes.forEach((item: string) => lines.push(`- ${item}`));
  }
  return lines.join("\n");
}

/** Merges the original free-text request with the student's answer to the
 * one clarifying question we asked about it. Plain concatenation here reads
 * as "both of these apply" even when the student's answer is actually a
 * correction (e.g. "python developer role" then, asked for more detail,
 * "html developer" — they meant "switch to HTML", not "combine Python and
 * HTML"). Telling the model a conflicting answer wins lets the free-text
 * interpretation already done in topic_generator_prompt resolve that
 * correctly instead of building a literal mashup of both. Kept short —
 * the backend's Course.name dedup key is capped at 255 chars (see
 * eligibility_check_free), and a shorter, cleaner string also stays a more
 * meaningful dedup key than a long one that gets truncated anyway. */
function combineWithClarifyingAnswer(originalRequest: string, answer: string): string {
  return `${answer} (a correction/follow-up to "${originalRequest}" — if they conflict, e.g. a different role or language, go with this one)`;
}

/** The actual eligibility+topic-generation call, shared by both the
 * "already specific enough" path and the "combined with the clarifying
 * answer" path below. `description` is what's actually sent to the LLM
 * (for the combined case, that includes instructional framing the student
 * shouldn't see); `displayLabel` — defaulting to the same text — is what
 * shows up in the chat message, so a combined request shows the student's
 * own words back to them instead of the raw merge instructions. */
async function generateTopicsFor(
  state: CapstoneFlowState,
  description: string,
  displayLabel: string = description,
): Promise<{ state: CapstoneFlowState; messages: CapstoneFlowMessage[] }> {
  try {
    const result = await checkEligibilityFree(state.name, state.email, state.phone, description, state.difficulty);
    const topics = result.topic_options ?? [];
    return {
      state: {
        ...state,
        pendingTopicSeed: undefined,
        topicSeed: displayLabel,
        threadId: result.thread_id,
        topicOptions: topics,
        step: "awaiting_topic_choice",
      },
      messages: [{
        text: `I generated two ${state.difficulty} project options for "${displayLabel}". Choose one to continue.`,
        options: topics.map((topic) => ({ label: `${topic.id}. ${topic.title}`, value: topic.id, description: topic.summary })),
      }],
    };
  } catch (error) {
    return {
      state: { ...state, pendingTopicSeed: undefined },
      messages: [{ text: `I could not generate a project for that: ${(error as Error).message}. Please try again.` }],
    };
  }
}

export async function handleCapstoneText(
  state: CapstoneFlowState,
  text: string,
): Promise<{ state: CapstoneFlowState; messages: CapstoneFlowMessage[] }> {
  const trimmed = text.trim();

  switch (state.step) {
    case "awaiting_topic_request": {
      if (!trimmed) {
        return { state, messages: [{ text: "Tell me the language, role, or topic you'd like your project based on." }] };
      }

      // Answering a clarifying question we already asked — combine it with
      // the original request and generate now. Capped at one round: we
      // don't re-run the clarity check on the combined description, even
      // if it's still vague, so this can never turn into a back-and-forth.
      if (state.pendingTopicSeed) {
        const combined = combineWithClarifyingAnswer(state.pendingTopicSeed, trimmed);
        return generateTopicsFor(state, combined, trimmed);
      }

      try {
        const clarity = await clarifyTopicRequest(trimmed);
        if (!clarity.ready && clarity.clarifying_question) {
          return {
            state: { ...state, pendingTopicSeed: trimmed },
            messages: [{ text: clarity.clarifying_question }],
          };
        }
      } catch {
        // Clarity check failing shouldn't block generation — fall through
        // and try to generate directly from what was typed, same as before
        // this feature existed.
      }
      return generateTopicsFor(state, trimmed);
    }

    case "awaiting_topic_choice": {
      const choice = trimmed.toUpperCase().replace(/[^AB]/g, "");
      const topic = state.topicOptions?.find((item) => item.id === choice);
      if (!topic) {
        return { state, messages: [{ text: "Choose project A or B.", options: state.topicOptions?.map((item) => ({ label: `${item.id}. ${item.title}`, value: item.id, description: item.summary })) }] };
      }
      try {
        const result = await chooseTopic(state.threadId!, topic.id);
        return {
          state: { ...state, chosenTopic: topic, requirements: result.requirements, step: "awaiting_timer_confirm" },
          messages: [{ text: `${formatRequirements(result.requirements)}\n\nStart the 7-day project timer when you are ready.`, options: [{ label: "Start 7-day timer", value: "confirm" }] }],
        };
      } catch (error) {
        return { state, messages: [{ text: `I could not lock that project: ${(error as Error).message}` }] };
      }
    }

    case "awaiting_timer_confirm": {
      if (!/^(confirm|yes|start)/i.test(trimmed)) return { state, messages: [{ text: "Use the button when you are ready. The timer cannot be paused.", options: [{ label: "Start 7-day timer", value: "confirm" }] }] };
      try {
        const result = await confirmTimer(state.threadId!);
        return {
          state: { ...state, deadlineAt: result.deadline_at, submissionGuide: result.submission_guide, step: "awaiting_submission" },
          messages: [{ text: `${formatSubmissionGuide(result.submission_guide, result.deadline_at)}\n\nI will monitor your project here. Attach the .docx report and .zip source code in this chat when ready.` }],
        };
      } catch (error) {
        return { state, messages: [{ text: `I could not start the timer: ${(error as Error).message}`, options: [{ label: "Try again", value: "confirm" }] }] };
      }
    }

    case "awaiting_viva_answer": {
      if (!trimmed) {
        return { state, messages: [{ text: "Please answer the question above before continuing." }] };
      }
      if (!state.vivaSubmissionId || state.vivaQuestionId == null) {
        return { state, messages: [{ text: "I lost track of the viva session. Please resubmit your project." }] };
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
          },
          messages: [{ text: `Score: ${result.final_score ?? "-"}/100 - Viva: ${result.viva_score ?? "-"}/10 - ${result.passed ? "You passed!" : "Not passed"}\n\n${result.feedback ?? ""}` }],
        };
      } catch (error) {
        return { state, messages: [{ text: `I could not record that answer: ${(error as Error).message}` }] };
      }
    }
    case "awaiting_submission":
      return { state, messages: [{ text: "Attach both your .docx report and .zip source archive using the paperclip button." }] };
    case "not_eligible":
      return { state, messages: [{ text: "This project request could not proceed. Start a new chat to try again." }] };
    case "graded":
      return { state, messages: [{ text: "This project has already been graded. Open the dashboard to review the result." }] };
  }
}

/** Re-runs topic generation for a new difficulty level after topics were
 * already generated (connector pill level change on awaiting_topic_choice).
 * A no-op with a friendly message outside that window — regeneration needs
 * the original topic seed, and once a topic is chosen the level is already
 * baked into the locked requirements. */
export async function regenerateTopicsForDifficulty(
  state: CapstoneFlowState,
  difficulty: ProjectDifficulty,
): Promise<{ state: CapstoneFlowState; messages: CapstoneFlowMessage[] }> {
  if (state.step !== "awaiting_topic_choice" || !state.topicSeed) {
    return { state: { ...state, difficulty }, messages: [] };
  }
  try {
    const result = await checkEligibilityFree(state.name, state.email, state.phone, state.topicSeed, difficulty);
    const topics = result.topic_options ?? [];
    return {
      state: { ...state, difficulty, threadId: result.thread_id, topicOptions: topics },
      messages: [{
        text: `Switched to ${difficulty} difficulty. I generated two new ${difficulty} project options for "${state.topicSeed}". Choose one to continue.`,
        options: topics.map((topic) => ({ label: `${topic.id}. ${topic.title}`, value: topic.id, description: topic.summary })),
      }],
    };
  } catch (error) {
    return { state, messages: [{ text: `I could not regenerate projects at ${difficulty} difficulty: ${(error as Error).message}` }] };
  }
}

export function mergeCapstoneFiles(state: CapstoneFlowState, files: File[]): { state: CapstoneFlowState; messages: CapstoneFlowMessage[] } {
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
        },
        messages: [{
          text: `Your project passed content grading. Before your score is revealed, a short viva (${result.viva_progress}): \n\n${result.viva_question.question}`,
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
