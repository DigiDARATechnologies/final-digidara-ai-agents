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
