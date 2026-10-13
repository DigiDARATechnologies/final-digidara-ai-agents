/**
 * Voice in, voice out: when the learner asks the DigiDARA Assistant a
 * question with the microphone, its reply is read aloud. The question is
 * marked here when it is sent by voice; the chat view takes the mark when the
 * reply arrives. A typed question clears it, so it is never spoken.
 */
const WAIT_MS = 90_000;
let expectedUntil = 0;

export function expectSpokenReply(): void {
  expectedUntil = Date.now() + WAIT_MS;
}

export function cancelSpokenReply(): void {
  expectedUntil = 0;
}

/** True once for the reply to a question asked by voice. */
export function takeSpokenReply(): boolean {
  const expected = Date.now() < expectedUntil;
  expectedUntil = 0;
  return expected;
}
