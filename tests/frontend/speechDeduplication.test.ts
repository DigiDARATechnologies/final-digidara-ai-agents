import { mergeCumulativeText } from '../../src/hooks/useSpeechRecognition';

describe('mergeCumulativeText mobile speech deduplication', () => {
  test('prevents Turn 1 duplicate (hello -> hello hello)', () => {
    const existing = 'hello';
    const incoming = 'hello';
    expect(mergeCumulativeText(existing, incoming)).toBe('hello');
  });

  test('prevents Turn 2 stutter cascade (hello -> hello are you hear me)', () => {
    let current = 'hello';
    current = mergeCumulativeText(current, 'hello are');
    expect(current).toBe('hello are');

    current = mergeCumulativeText(current, 'hello are you');
    expect(current).toBe('hello are you');

    current = mergeCumulativeText(current, 'hello are you hear me');
    expect(current).toBe('hello are you hear me');
  });

  test('prevents Turn 3 massive MNC duplication from PDF', () => {
    let current = '';
    const androidEvents = [
      'MNC',
      'MNC anything',
      'MNC anything can',
      'MNC anything can you',
      'MNC anything can you please',
      'MNC anything can you please stop',
      'MNC anything can you please stop the',
      'MNC anything can you please stop the conversation',
    ];

    for (const eventText of androidEvents) {
      current = mergeCumulativeText(current, eventText);
    }

    expect(current).toBe('MNC anything can you please stop the conversation');
  });

  test('merges distinct sequential sentences with a space', () => {
    const a = 'I live in Chennai.';
    const b = 'It is a nice city.';
    expect(mergeCumulativeText(a, b)).toBe('I live in Chennai. It is a nice city.');
  });

  test('merges boundary word overlaps cleanly', () => {
    const a = 'I like eating';
    const b = 'eating healthy food';
    expect(mergeCumulativeText(a, b)).toBe('I like eating healthy food');
  });
});
