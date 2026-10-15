/**
 * "Just a minute", "wait", "let me think"... said during spoken practice:
 * the learner wants more time, so their answer is not sent yet. Whatever
 * they said before the phrase is kept, and their next words are added to it.
 */
const HOLD = /(?:^|[\s,.!?])(?:just\s+)?(?:a|one|give\s+me\s+a|wait\s+a|hold\s+on\s+a)?\s*(?:minute|min|moment|second|sec)(?:\s+please)?|(?:^|[\s,.!?])(?:wait|hold\s+on|let\s+me\s+think|let\s+me\s+see)(?:\s+please)?/i;
const AT_END = new RegExp(`(?:${HOLD.source})[\\s.!?,]*$`, "i");

/** True when the learner asked for more time at the end of what they said. */
export function isHoldRequest(text: string): boolean {
  return AT_END.test(text.trim());
}

/** What they said before asking for more time ("" if only the phrase). */
export function withoutHoldPhrase(text: string): string {
  return text.trim().replace(AT_END, "").replace(/[\s,]+$/, "").trim();
}

/** The answer so far plus the newest words. */
export function joinAnswer(before: string, next: string): string {
  return [before.trim(), next.trim()].filter(Boolean).join(" ");
}

/** "Hold on, I am not completing" said at the start of a new turn: the learner
 * is not done with what they were saying, so what they said before carries on. */
const CONTINUATION = /^(?:(?:just|please|sorry|no|wait|okay|ok|sir)[\s,.!]+)*(?:hold\s+on|wait|one\s+(?:sec(?:ond)?|minute|moment)|a\s+(?:sec(?:ond)?|minute|moment)|(?:i\s*(?:am|'m|m)|i\s+have(?:n'?t| not))\s*(?:not\s+)?(?:yet\s+)?(?:done|finished|completed?|completing|finishing|complete)(?:\s+yet)?|let\s+me\s+(?:finish|complete|continue)|i\s+(?:was|am)\s+(?:saying|still\s+(?:saying|talking|speaking)))\b[\s,.!]*(?:i\s*(?:am|'m|m)\s*(?:not\s+)?(?:yet\s+)?(?:done|finished|completed?|completing|finishing|complete)\b[\s,.!]*)?/i;

/** True when this turn begins by saying the previous one is not finished. */
export function isContinuation(text: string): boolean {
  return CONTINUATION.test(text.trim());
}

/** What follows the "hold on, I am not completing" opening ("" if nothing). */
export function afterContinuation(text: string): string {
  return text.trim().replace(CONTINUATION, "").replace(/^[\s,.!]+/, "").trim();
}
