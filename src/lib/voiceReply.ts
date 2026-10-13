/**
 * A voice conversation started on the new-chat screen carries on in the chat
 * it creates: the screen marks it here when it sends the first question, and
 * the chat view takes the mark when it opens, so the conversation continues
 * (waiting for that question's reply) instead of ending.
 */
const WAIT_MS = 30_000;
let continueUntil = 0;

export function continueVoiceConversation(): void {
  continueUntil = Date.now() + WAIT_MS;
}

export function cancelVoiceConversation(): void {
  continueUntil = 0;
}

let conversationOpen = false;

/** The voice conversation is on screen: Boss's replies are kept short and spoken. */
export function setVoiceConversationOpen(open: boolean): void {
  conversationOpen = open;
}

export function isVoiceConversationOpen(): boolean {
  return conversationOpen;
}

/** True once, for the chat opened by a voice conversation's first question. */
export function takeVoiceConversation(): boolean {
  const continuing = Date.now() < continueUntil;
  continueUntil = 0;
  return continuing;
}
