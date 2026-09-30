import {
  removeMobileTranscriptLoops,
  updateSpeechResultSlots,
  type SpeechResultSnapshot,
} from '../../src/lib/speechTranscript';

type ResultInput = { text: string; final: boolean };

function event(resultIndex: number, inputs: ResultInput[]) {
  return {
    resultIndex,
    results: inputs.map(({ text, final }) => ({
      isFinal: final,
      0: { transcript: text, confidence: 0.9 },
    })),
  };
}

test('growing mobile interim results replace their result slot instead of accumulating', () => {
  const slots = new Map<number, SpeechResultSnapshot>();
  expect(updateSpeechResultSlots(slots, event(0, [{ text: 'the view', final: false }])).displayText).toBe('the view');
  expect(updateSpeechResultSlots(slots, event(0, [{ text: 'the view in', final: false }])).displayText).toBe('the view in');
  expect(updateSpeechResultSlots(slots, event(0, [{ text: 'the view in Django', final: true }])).displayText).toBe('the view in Django');
});

test('a re-emitted final result index replaces the earlier mobile result', () => {
  const slots = new Map<number, SpeechResultSnapshot>();
  updateSpeechResultSlots(slots, event(0, [{ text: 'variable', final: true }]));
  const result = updateSpeechResultSlots(slots, event(0, [{ text: 'A variable stores a value', final: true }]));
  expect(result.finalText).toBe('A variable stores a value');
});

test('separate final and interim slots assemble once in their original order', () => {
  const slots = new Map<number, SpeechResultSnapshot>();
  updateSpeechResultSlots(slots, event(0, [
    { text: 'A primary key', final: true },
    { text: 'uniquely', final: false },
  ]));
  const result = updateSpeechResultSlots(slots, event(1, [
    { text: 'A primary key', final: true },
    { text: 'uniquely identifies each row', final: true },
  ]));
  expect(result.displayText).toBe('A primary key uniquely identifies each row');
  expect(result.finalText).toBe('A primary key uniquely identifies each row');
});

test('cumulative phrases emitted in later mobile result slots are not duplicated', () => {
  const slots = new Map<number, SpeechResultSnapshot>();
  const result = updateSpeechResultSlots(slots, event(0, [
    { text: 'The view in Django', final: true },
    { text: 'The view in Django handles a request', final: true },
  ]));
  expect(result.finalText).toBe('The view in Django handles a request');
});

test('an exact replay in a later result slot is included only once', () => {
  const slots = new Map<number, SpeechResultSnapshot>();
  const result = updateSpeechResultSlots(slots, event(0, [
    { text: 'A URL identifies an endpoint', final: true },
    { text: 'A URL identifies an endpoint', final: true },
  ]));
  expect(result.finalText).toBe('A URL identifies an endpoint');
});

test('removes a phone recognizer word loop after three repetitions', () => {
  expect(removeMobileTranscriptLoops('No no no no, thank you.')).toBe('No thank you.');
});

test('removes a repeated mobile phrase despite punctuation differences', () => {
  expect(removeMobileTranscriptLoops('Batter, no. Batter, no. Batter, no. Batter, no.'))
    .toBe('Batter, no.');
});

test('keeps natural two-time emphasis unchanged', () => {
  expect(removeMobileTranscriptLoops('No no, I would like to play.'))
    .toBe('No no, I would like to play.');
});
