/** Wording of questions put to Boss (no network, so it is unit-testable). */
/** "Hey Boss, what is wrong here?" -> "what is wrong here?" (the wake words are not part of the question). */
export function withoutWakeWords(text: string): string {
  return text.replace(/^\s*(?:(?:hey|hi|hello|ok|okay)[\s,]+)?boss\b[\s,.!:-]*/i, "").trim();
}

/** The question points at the screen ("what is wrong here", "look at this", "explain this error"). */
export function refersToScreen(text: string): boolean {
  return /\b(screen|screenshot|page|here|this|these|that|error|see|look|showing|shown|wrong|stuck)\b/i.test(text);
}
