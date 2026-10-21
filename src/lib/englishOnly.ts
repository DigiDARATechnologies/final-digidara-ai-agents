/**
 * Every DigiDARA agent works in English only. The same script check as the
 * server (agents/orchestrator/app/english_only.py): Tamil, Hindi, Telugu,
 * Malayalam, Kannada, Arabic, Chinese and other non-English scripts are
 * refused; Latin letters, accents, digits, emoji and math symbols are fine.
 */
export const ENGLISH_ONLY_MESSAGE = "Please type in English. DigiDARA agents understand and reply in English only.";

const OTHER_SCRIPTS =
  /[Ѐ-ԯ֐-׿؀-ۿ܀-ࣿऀ-෿฀-࿿က-႟Ⴀ-ჿᄀ-ᇿក-៿぀-ヿ㄰-㆏㐀-䶿一-鿿꣠-ꣿ가-힯יִ-﷿ﹰ-﻿]|\uD807[\uDFC0-\uDFFF]/;

export function isEnglishText(text: string): boolean {
  return !OTHER_SCRIPTS.test(text);
}
