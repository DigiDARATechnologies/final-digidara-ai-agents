jest.mock('../../src/lib/session', () => ({ sessionToken: () => 'token' }));
jest.mock('../../src/lib/voiceApiBase', () => ({ VOICE_API_BASE: 'http://api.test' }));

// The voice element: plays when asked and ends when the test says so.
const mockPlayers: FakeAudio[] = [];
class FakeAudio {
  src = '';
  preload = '';
  volume = 1;
  playbackRate = 1;
  crossOrigin: string | null = null;
  dataset: Record<string, string> = {};
  onplaying: (() => void) | null = null;
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor() { mockPlayers.push(this); }
  play() { setTimeout(() => this.onplaying?.(), 0); return Promise.resolve(); }
  pause() {}
  load() {}
  removeAttribute() {}
}

const spoken: string[] = [];
beforeEach(() => {
  jest.useFakeTimers();
  mockPlayers.length = 0;
  spoken.length = 0;
  (globalThis as unknown as { Audio: typeof FakeAudio }).Audio = FakeAudio;
  globalThis.fetch = jest.fn(async (_url: string, init?: { body?: string }) => {
    spoken.push(JSON.parse(init?.body || '{}').text);
    return { ok: true, json: async () => ({ url: `/voice/stream/${spoken.length}` }) } as Response;
  }) as unknown as typeof fetch;
});
afterEach(() => jest.useRealTimers());

import { createSpeechQueue, stopSpeaking } from '../../src/lib/voiceEngine';

async function flush(ms = 0) {
  await jest.advanceTimersByTimeAsync(ms);
}

test('after the opening words, the rest of a streamed reply is made as one piece, not clause by clause', async () => {
  const onEnd = jest.fn();
  const queue = createSpeechQueue({ onEnd }, true);
  queue.push('Yes, I am right here.');
  await flush();
  expect(spoken).toEqual(['Yes, I am right here.']);
  // The reply keeps arriving while the opening plays.
  queue.push('You have completed eight aptitude tests,');
  queue.push('and your best score was seventy four percent.');
  queue.push('Shall I open the Aptitude Trainer?');
  queue.end();
  await flush(400);
  expect(spoken).toEqual([
    'Yes, I am right here.',
    'You have completed eight aptitude tests, and your best score was seventy four percent. Shall I open the Aptitude Trainer?',
  ]);
  mockPlayers[0].onended?.();
  await flush();
  mockPlayers[1].onended?.();
  await flush();
  expect(onEnd).toHaveBeenCalledTimes(1);
  stopSpeaking();
});
