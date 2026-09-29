import { AFTER_PROMPT_END_MS, NO_SPEECH_PROMPT_MS, SPOKEN_PAUSE_SUBMIT_MS, secondsUntilAction, silenceAction } from '../../src/lib/answerSilence';

const base = { now: 100_000, answeringSince: 100_000, lastVoiceAt: null, promptedAt: null, manual: false };

test('after speaking, a 5 second pause submits the answer', () => {
  expect(silenceAction({ ...base, now: 100_000 + SPOKEN_PAUSE_SUBMIT_MS - 1, lastVoiceAt: 100_000 })).toBe('none');
  expect(silenceAction({ ...base, now: 100_000 + SPOKEN_PAUSE_SUBMIT_MS, lastVoiceAt: 100_000 })).toBe('submit');
});

test('without any speech, "are you there?" is asked after 30 seconds, and the interview ends 15 seconds later', () => {
  expect(silenceAction({ ...base, now: 100_000 + NO_SPEECH_PROMPT_MS - 1 })).toBe('none');
  expect(silenceAction({ ...base, now: 100_000 + NO_SPEECH_PROMPT_MS })).toBe('prompt');
  const prompted = 100_000 + NO_SPEECH_PROMPT_MS;
  expect(silenceAction({ ...base, now: prompted + AFTER_PROMPT_END_MS - 1, promptedAt: prompted })).toBe('none');
  expect(silenceAction({ ...base, now: prompted + AFTER_PROMPT_END_MS, promptedAt: prompted })).toBe('end');
});

test('typing, a paused microphone, or no microphone stops every automatic action', () => {
  expect(silenceAction({ ...base, now: 200_000, lastVoiceAt: 100_000, manual: true })).toBe('none');
  expect(silenceAction({ ...base, now: 200_000, promptedAt: 100_000, manual: true })).toBe('none');
  expect(silenceAction({ ...base, now: 200_000, manual: true })).toBe('none');
});

test('the countdown shows only in the last 3 seconds before submitting, and throughout after the prompt', () => {
  expect(secondsUntilAction({ ...base, now: 101_000, lastVoiceAt: 100_000 })).toBeNull();
  expect(secondsUntilAction({ ...base, now: 102_500, lastVoiceAt: 100_000 })).toEqual({ action: 'submit', seconds: 3 });
  expect(secondsUntilAction({ ...base, now: 105_000, promptedAt: 100_000 })).toEqual({ action: 'end', seconds: 10 });
});
