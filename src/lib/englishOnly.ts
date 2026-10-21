/**
 * Every DigiDARA agent works in English only. The same script check as the
 * server (agents/orchestrator/app/english_only.py): Tamil, Hindi, Telugu,
 * Malayalam, Kannada, Arabic, Chinese and other non-English scripts are
 * refused; Latin letters, accents, digits, emoji and math symbols are fine.
 */
export const ENGLISH_ONLY_MESSAGE = "Please type in English. DigiDARA agents understand and reply in English only.";
/** Shown and said aloud when a learner speaks another language (same text as the server). */
export const SPEAK_ENGLISH_MESSAGE = "I only understand English. Could you please speak in English?";

const OTHER_SCRIPTS =
  /[\u0400-\u052F\u0590-\u05FF\u0600-\u06FF\u0700-\u08FF\u0900-\u0DFF\u0E00-\u0FFF\u1000-\u109F\u10A0-\u10FF\u1100-\u11FF\u1780-\u17FF\u3040-\u30FF\u3130-\u318F\u3400-\u4DBF\u4E00-\u9FFF\uA8E0-\uA8FF\uAC00-\uD7AF\uFB1D-\uFDFF\uFE70-\uFEFF]|\uD807[\uDFC0-\uDFFF]/;

/** The microphone picked up the agent's own "please speak in English" notice. */
export function isEnglishNoticeEcho(text: string): boolean {
  return /only understand english/i.test(text);
}

export function isEnglishText(text: string): boolean {
  return !OTHER_SCRIPTS.test(text);
}
