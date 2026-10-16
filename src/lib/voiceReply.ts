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

/** The chat opened for a voice conversation that has not asked anything yet:
 * the chat view takes this mark and opens the conversation with Boss's greeting. */
let greetUntil = 0;

export function startVoiceGreeting(): void {
  greetUntil = Date.now() + WAIT_MS;
}

export function takeVoiceGreeting(): boolean {
  const greeting = Date.now() < greetUntil;
  greetUntil = 0;
  return greeting;
}

let conversationOpen = false;
const openListeners = new Set<(open: boolean) => void>();

/** The voice conversation is on screen: Boss's replies are kept short and spoken. */
export function setVoiceConversationOpen(open: boolean): void {
  conversationOpen = open;
  for (const listener of [...openListeners]) listener(open);
}

/** Told whenever the voice conversation opens or closes ("Hey Boss" waits
 * while it is closed). Returns unsubscribe. */
export function onVoiceConversationOpen(listener: (open: boolean) => void): () => void {
  openListeners.add(listener);
  return () => { openListeners.delete(listener); };
}

/** "Hey Boss" heard on a screen that is Boss's own (the new-chat screen, the
 * Boss chat): that screen opens Boss's voice conversation, with what was said
 * after the wake words as the first question. */
let bossVoiceOpener: ((question: string) => void) | null = null;

export function setBossVoiceOpener(opener: ((question: string) => void) | null): () => void {
  bossVoiceOpener = opener;
  return () => { if (bossVoiceOpener === opener) bossVoiceOpener = null; };
}

/** True when a Boss screen took the wake words and opened its conversation. */
export function openBossVoice(question: string): boolean {
  if (!bossVoiceOpener) return false;
  bossVoiceOpener(question);
  return true;
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
