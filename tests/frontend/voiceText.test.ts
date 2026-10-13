import { speakableText, splitForSpeech } from '../../src/lib/voiceText';

test('speaks the words, not the markdown, links, code or emoji', () => {
  const reply = '## Great job! 🎉\n- **Score:** 8/10\n- See [your report](https://x.test/r)\n```python\nprint(1)\n```\nKeep going `daily`.';
  expect(speakableText(reply)).toBe('Great job! Score: 8/10 See your report Keep going daily.');
});

test('the first piece is short so speech starts quickly, later pieces group sentences', () => {
  const text = 'Hello Asha. ' + 'This is a longer explanation of your interview answer. '.repeat(6);
  const chunks = splitForSpeech(text.trim());
  expect(chunks[0].length).toBeLessThanOrEqual(100);
  expect(chunks.every((c) => c.length <= 260)).toBe(true);
  expect(chunks.join(' ').replace(/\s+/g, ' ')).toBe(text.trim().replace(/\s+/g, ' '));
});

test('Tamil sentences split on their own full stops and question marks', () => {
  const chunks = splitForSpeech('வணக்கம்! இன்று SQL பயிற்சி செய்யலாமா? நீங்கள் நன்றாக செய்கிறீர்கள்.');
  expect(chunks.join(' ')).toContain('வணக்கம்!');
  expect(chunks.length).toBeGreaterThanOrEqual(1);
});

test('a very long sentence is cut at commas and spaces, never mid-word', () => {
  const words = Array.from({ length: 120 }, (_, i) => `word${i}`).join(' ');
  const chunks = splitForSpeech(words);
  expect(chunks.every((c) => c.length <= 260)).toBe(true);
  expect(chunks.join(' ').split(' ')).toEqual(words.split(' '));
});

test('a long opening sentence is spoken clause first', () => {
  const chunks = splitForSpeech('That was a strong answer about your final-year project, and you explained the database design clearly, which interviewers love.');
  expect(chunks[0]).toBe('That was a strong answer about your final-year project,');
  expect(chunks.join(' ')).toContain('which interviewers love.');
});
