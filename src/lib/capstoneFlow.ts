import { CAPSTONE_EXAMPLE_OPTIONS } from "./capstoneExamples";
import type { ChatOption, User } from "../types";
import {
  askProjectQuestion,
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
 * HTML"). Earlier wording told the model the newer answer wins whenever the
 * two "conflict" — but that framing was too eager: given a non-conflicting
 * pair like "portfolio website" then "python", the model still dropped
 * "portfolio website" entirely and generated generic Python topics instead
 * of a Python-based portfolio site. Spelling out that most answers are
 * *additions*, and only a genuinely different role/language/domain is a
 * replacement, keeps the free-text interpretation in topic_generator_prompt
 * from over-applying the override case. Kept short — the backend's
 * Course.name dedup key is capped at 255 chars (see eligibility_check_free),
 * and a shorter, cleaner string also stays a more meaningful dedup key than
 * a long one that gets truncated anyway. */
/** A deferral ("your choice", "you decide", "surprise me", "idk") answers
 * the clarifying question by declining to add any actual content — it is
 * never itself a role/language/domain detail, so appending it literally
 * (as "python — your choice") reads back to the student as if "your choice"
 * were part of their request, and gives the topic-generator LLM nothing
 * useful to combine. Detected up front so the original request is passed
 * through alone, with a note that the student left this open, instead of
 * being combined at all. */
const DEFERRAL_ANSWER = /^(your|you'?re|any|the)?\s*(choice|pick|call|decision)\b|^you\s*(decide|choose|pick)\b|^(up to you|surprise me|whatever|anything('?s| is)? (fine|works|good)|no preference|i don'?t (know|care|mind)|idk|not sure|either (is fine|works)|doesn'?t matter)\b/i;

function combineWithClarifyingAnswer(originalRequest: string, answer: string): string {
  if (DEFERRAL_ANSWER.test(answer.trim())) {
    return `${originalRequest} (the student was asked a clarifying follow-up about this and declined to add any more detail — use your own best judgment for whatever it was asking about)`;
  }
  return `${originalRequest} — additional detail from a follow-up question: "${answer}" (combine both; only drop "${originalRequest}" if "${answer}" genuinely names a different role, language, or domain instead of the same one)`;
}

/** What the chat should show as "the request" once a clarifying answer is
 * folded in — a deferral contributes no content of its own, so the original
 * request is shown alone rather than as "python — your choice". */
function displayLabelForClarifyingAnswer(originalRequest: string, answer: string): string {
  return DEFERRAL_ANSWER.test(answer.trim()) ? originalRequest : `${originalRequest} — ${answer}`;
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
        return generateTopicsFor(state, combined, displayLabelForClarifyingAnswer(state.pendingTopicSeed, trimmed));
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
      // Only an actual selection ("A", "b", "option A", "A.") should count --
      // stripping the text down to whichever of the letters A/B it happens to
      // contain (the previous approach) silently mis-selected a project for
      // any unrelated message that merely used the letter "a" somewhere, e.g.
      // "I need to change the project topics" collapsing to "A".
      const match = trimmed.match(/^(?:option\s*)?([ab])\.?$/i);
      const choice = match ? match[1].toUpperCase() : null;
      const topic = choice ? state.topicOptions?.find((item) => item.id === choice) : undefined;
      if (!topic) {
        const options = state.topicOptions?.map((item) => ({ label: `${item.id}. ${item.title}`, value: item.id, description: item.summary }));
        // A genuine question about the two options gets a real answer; a
        // message that's neither a valid selection nor recognizably a
        // question (small talk, an unrelated request) just gets steered
        // back to choosing -- the Q&A agent itself declines anything
        // unrelated to this project, so this never turns into open chat.
        if (state.threadId && trimmed && looksLikeQuestionOrDispute(trimmed)) {
          try {
            const qa = await askProjectQuestion(state.threadId, trimmed);
            return { state, messages: [{ text: qa.answer }, { text: "Choose project A or B to continue.", options }] };
          } catch {
            // Q&A itself failed -- fall through to the plain reminder below.
          }
        }
        return { state, messages: [{ text: "Choose project A or B.", options }] };
      }
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

    case "awaiting_timer_confirm": {
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
          } catch {
            // Q&A itself failed -- fall through to the plain reminder below.
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
    case "awaiting_submission": {
      // A student disputing a revision note ("already have the approach
      // section") deserves an actual answer grounded in their submission,
      // not the same canned reminder every other message gets here.
      if (state.threadId && trimmed && looksLikeQuestionOrDispute(trimmed)) {
        try {
          const qa = await askProjectQuestion(state.threadId, trimmed);
          return { state, messages: [{ text: qa.answer }, { text: "Attach both your .docx report and .zip source archive using the paperclip button when you're ready to resubmit." }] };
        } catch {
          // Q&A itself failed -- fall through to the normal reminder below.
        }
      }
      return { state, messages: [{ text: "Attach both your .docx report and .zip source archive using the paperclip button." }] };
    }
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
