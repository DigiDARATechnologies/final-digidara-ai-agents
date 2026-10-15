import { formatSpeakingTurn, parseSpeakingTurn, speakingTurnSpeech } from '../../src/lib/speakingTurn';
import { cancelVoiceConversation, continueVoiceConversation, takeVoiceConversation } from '../../src/lib/voiceReply';

const turn = {
  said: 'Yeah so like I completed my chemistry',
  better: 'I completed my degree in chemistry.',
  comment: "That's interesting!",
  next: 'What areas of software development interest you?',
};

test('a speaking turn is shown and parsed back in four separate parts', () => {
  const text = formatSpeakingTurn(turn);
  expect(text.split('\n\n')).toHaveLength(4);
  expect(parseSpeakingTurn(text)).toEqual(turn);
});

test('without a correction only the other parts are shown', () => {
  const parsed = parseSpeakingTurn(formatSpeakingTurn({ ...turn, better: '' }));
  expect(parsed).toEqual({ ...turn, better: '' });
});

test('other messages are not speaking turns', () => {
  expect(parseSpeakingTurn('Tell me about yourself.')).toBeNull();
});

test('the coach speaks the comment, the better sentence and the next question, not the learner\'s words', () => {
  const speech = speakingTurnSpeech(turn);
  expect(speech).toContain('A better way to say it: I completed my degree in chemistry.');
  expect(speech).toContain(turn.next);
  expect(speech).not.toContain(turn.said);
});

test('a voice conversation started on the new-chat screen carries on once in the chat it opens', () => {
  expect(takeVoiceConversation()).toBe(false);
  continueVoiceConversation();
  expect(takeVoiceConversation()).toBe(true);
  expect(takeVoiceConversation()).toBe(false);
  continueVoiceConversation();
  cancelVoiceConversation();
  expect(takeVoiceConversation()).toBe(false);
});

test('only finished sentences of a reply that is still being written are spoken', () => {
  const { completeSentences } = jest.requireActual('../../src/lib/voiceText') as typeof import('../../src/lib/voiceText');
  expect(completeSentences('Hi there! I am Bo', 0)).toEqual({ text: 'Hi there!', next: 9 });
  expect(completeSentences('Hi there! I am Boss. Ask', 9)).toEqual({ text: ' I am Boss.', next: 20 });
  expect(completeSentences('Version 2.5 is', 0)).toEqual({ text: '', next: 0 });
  expect(completeSentences('Steps:\n1. Open it', 0)).toEqual({ text: 'Steps:\n', next: 7 });
});

test('streamed replies are spoken from the first few words, never cutting a word', () => {
  const { readyToSpeak } = jest.requireActual('../../src/lib/voiceText') as typeof import('../../src/lib/voiceText');
  // Too little yet: wait.
  expect(readyToSpeak('Sure, I can help', 0, true)).toEqual({ text: '', next: 0 });
  // Enough opening words: speak them, leaving the word still arriving ("deve").
  expect(readyToSpeak('Sure, I can help you with your deve', 0, true)).toEqual({ text: 'Sure, I can help you with your', next: 30 });
  // A finished sentence still goes as a whole.
  expect(readyToSpeak('Hi there! I am Bo', 0, true)).toEqual({ text: 'Hi there!', next: 9 });
  // Later text: a finished clause is spoken, an unfinished one waits.
  expect(readyToSpeak(' and then you can open the resume builder, which', 0, false)).toEqual({ text: ' and then you can open the resume builder,', next: 42 });
  expect(readyToSpeak(' and then you can open the resume builder which', 0, false)).toEqual({ text: '', next: 0 });
});

test('"hold on, I am not completing" is a continuation of the previous question', () => {
  const { isContinuation, afterContinuation } = jest.requireActual('../../src/lib/holdPhrase') as typeof import('../../src/lib/holdPhrase');
  expect(isContinuation('just hold on i am not completing')).toBe(true);
  expect(afterContinuation('just hold on i am not completing')).toBe('');
  expect(isContinuation("wait, I'm not done yet, also tell me about jobs")).toBe(true);
  expect(afterContinuation("wait, I'm not done yet, also tell me about jobs")).toBe('also tell me about jobs');
  expect(isContinuation('let me finish. and the interview agent')).toBe(true);
  expect(afterContinuation('let me finish. and the interview agent')).toBe('and the interview agent');
  // An ordinary new question is not a continuation.
  expect(isContinuation('what is the resume builder')).toBe(false);
  expect(isContinuation('how long should I wait for results')).toBe(false);
});
