/**
 * One Speaking Practice turn, kept in four labelled parts so the screen can
 * show them separately: what the learner said, a better way to say it, the
 * coach's comment, and the next question.
 */
export interface SpeakingTurn {
  said: string;
  better: string;
  comment: string;
  next: string;
}

const SAID = "🗣️ You said:";
const BETTER = "✅ Better way to say it:";
const COMMENT = "💬 Coach:";
const NEXT = "❓ Next question:";

const unquote = (value: string) => value.trim().replace(/^[“"]+|[”"]+$/g, "").trim();

export function formatSpeakingTurn(turn: SpeakingTurn): string {
  return [
    turn.said ? `${SAID} “${turn.said}”` : "",
    turn.better ? `${BETTER} “${turn.better}”` : "",
    turn.comment ? `${COMMENT} ${turn.comment}` : "",
    `${NEXT} ${turn.next}`,
  ].filter(Boolean).join("\n\n");
}

/** The four parts of a formatted turn, or null for any other message. */
export function parseSpeakingTurn(text: string): SpeakingTurn | null {
  if (!text.includes(NEXT)) return null;
  const part = (label: string) => {
    const start = text.indexOf(label);
    if (start < 0) return "";
    const rest = text.slice(start + label.length);
    const end = [SAID, BETTER, COMMENT, NEXT]
      .map((other) => rest.indexOf(`\n\n${other}`))
      .filter((index) => index >= 0);
    return rest.slice(0, end.length ? Math.min(...end) : undefined).trim();
  };
  return { said: unquote(part(SAID)), better: unquote(part(BETTER)), comment: part(COMMENT), next: part(NEXT) };
}

/** What the coach says aloud: the comment, the better sentence and the next
 * question -- not the learner's own words read back to them. */
export function speakingTurnSpeech(turn: SpeakingTurn): string {
  return [
    turn.comment,
    turn.better ? `A better way to say it: ${turn.better}` : "",
    turn.next,
  ].filter(Boolean).join(" ");
}
