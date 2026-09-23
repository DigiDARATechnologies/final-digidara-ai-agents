/** Browser SpeechSynthesis helpers used by the voice interview flow. */

let speechUnlocked = false;

function getSpeechSynthesis(): SpeechSynthesis | null {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  return window.speechSynthesis;
}

/**
 * Prime the browser speech engine from a real user gesture. Chrome and Edge
 * can otherwise reject speech started later from an async React effect.
 */
export function unlockSpeechSynthesis(): boolean {
  const synthesis = getSpeechSynthesis();
  if (!synthesis) return false;

  try {
    synthesis.resume();
    // A silent utterance establishes an allowed speech session without
    // producing an audible prompt before the interview question is ready.
    const unlockUtterance = new SpeechSynthesisUtterance("");
    unlockUtterance.volume = 0;
    synthesis.speak(unlockUtterance);
    speechUnlocked = true;
    return true;
  } catch {
    return false;
  }
}

export function isSpeechSynthesisUnlocked(): boolean {
  return speechUnlocked;
}

/** Wait briefly for Chrome/Safari to publish voices after a fresh page load. */
export function waitForSpeechVoices(timeoutMs = 1200): Promise<void> {
  const synthesis = getSpeechSynthesis();
  if (!synthesis || synthesis.getVoices().length > 0) return Promise.resolve();

  return new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      synthesis.removeEventListener("voiceschanged", finish);
      window.clearTimeout(timer);
      resolve();
    };
    const timer = window.setTimeout(finish, timeoutMs);
    synthesis.addEventListener("voiceschanged", finish, { once: true });
  });
}

export async function speakBrowserText(
  text: string,
  handlers: {
    onStart?: () => void;
    onEnd?: () => void;
    onError?: (event: SpeechSynthesisErrorEvent) => void;
  } = {},
): Promise<boolean> {
  const synthesis = getSpeechSynthesis();
  if (!synthesis || typeof SpeechSynthesisUtterance === "undefined") return false;

  await waitForSpeechVoices();
  synthesis.resume();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 1;
  utterance.onstart = handlers.onStart ?? null;
  utterance.onend = handlers.onEnd ?? null;
  utterance.onerror = (event) => {
    handlers.onError?.(event);
    handlers.onEnd?.();
  };
  synthesis.cancel();
  try {
    synthesis.speak(utterance);
    return true;
  } catch (error) {
    handlers.onError?.(error as SpeechSynthesisErrorEvent);
    handlers.onEnd?.();
    return false;
  }
}
