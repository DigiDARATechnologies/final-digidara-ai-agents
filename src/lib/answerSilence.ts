/** What the Mock Interview does when the candidate goes quiet.
 *
 * - After they have started speaking, a pause of SPOKEN_PAUSE_SUBMIT_MS
 *   submits the answer: they have finished.
 * - If they have not said anything NO_SPEECH_PROMPT_MS after the question,
 *   they are asked "Hey, are you there?".
 * - If there is still nothing AFTER_PROMPT_END_MS after that, the interview
 *   ends.
 * Typing an answer, or pausing the microphone, hands control back to the
 * candidate: nothing happens automatically. */

export const SPOKEN_PAUSE_SUBMIT_MS = 5_000;
export const NO_SPEECH_PROMPT_MS = 30_000;
export const AFTER_PROMPT_END_MS = 15_000;

export const AWAY_PROMPT = "Hey, are you there?";

export type SilenceAction = "none" | "submit" | "prompt" | "end";

export interface SilenceState {
  now: number;
  /** When the answer window opened (after the question was read out). */
  answeringSince: number;
  /** The last moment the candidate was heard, or null if not yet this question. */
  lastVoiceAt: number | null;
  /** When "Hey, are you there?" was asked, or null if it has not been. */
  promptedAt: number | null;
  /** The candidate typed in the answer box or paused the microphone. */
  manual: boolean;
}

export function silenceAction({ now, answeringSince, lastVoiceAt, promptedAt, manual }: SilenceState): SilenceAction {
  if (manual) return "none";
  if (lastVoiceAt !== null) return now - lastVoiceAt >= SPOKEN_PAUSE_SUBMIT_MS ? "submit" : "none";
  if (promptedAt === null) return now - answeringSince >= NO_SPEECH_PROMPT_MS ? "prompt" : "none";
  return now - promptedAt >= AFTER_PROMPT_END_MS ? "end" : "none";
}

/** Whole seconds until the pending automatic action, for the on-screen hint;
 * null when nothing is about to happen (more than 3s away after speech, or
 * before the prompt). */
export function secondsUntilAction({ now, lastVoiceAt, promptedAt, manual }: SilenceState): { action: "submit" | "end"; seconds: number } | null {
  if (manual) return null;
  if (lastVoiceAt !== null) {
    const remaining = SPOKEN_PAUSE_SUBMIT_MS - (now - lastVoiceAt);
    return remaining <= 3_000 ? { action: "submit", seconds: Math.max(0, Math.ceil(remaining / 1000)) } : null;
  }
  if (promptedAt !== null) {
    return { action: "end", seconds: Math.max(0, Math.ceil((AFTER_PROMPT_END_MS - (now - promptedAt)) / 1000)) };
  }
  return null;
}
