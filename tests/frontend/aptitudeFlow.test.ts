jest.mock('../../src/lib/aptitudeApi', () => ({
  abandonAptitudeTest: jest.fn(), createAptitudeTest: jest.fn(),
  ensureAptitudeSession: jest.fn(), getAptitudeQuestion: jest.fn(),
  getAptitudeResults: jest.fn(), requestAptitudeHint: jest.fn(),
  submitAptitudeAnswer: jest.fn(), downloadAptitudeReport: jest.fn(),
  skipAptitudeQuestion: jest.fn(),
}));
import { createInitialAptitudeState, handleAptitudeText, type AptitudeFlowState } from '../../src/lib/aptitudeFlow';
import * as api from '../../src/lib/aptitudeApi';

const question: api.AptitudeQuestion = { test_id: 'test', sequence: 1, total_questions: 10, category: 'Logical Reasoning', topic: 'Patterns', difficulty: 'Easy', question: 'Which pattern?', options: { A: 'First', B: 'Second' }, allowed_time_seconds: 60, hints_remaining: 2 };
const active: AptitudeFlowState = { step: 'awaiting_question', sessionToken: 'session', testId: 'test', question };

test.each([['mixed', 'awaiting_language'], ['category practice', 'awaiting_category']])('selects %s mode', async (input, step) => {
  const result = await handleAptitudeText(createInitialAptitudeState(), input);
  expect(result.state.step).toBe(step);
  expect(api.createAptitudeTest).not.toHaveBeenCalled();
});

test('rejects unknown mode without creating a test', async () => {
  const result = await handleAptitudeText(createInitialAptitudeState(), 'anything');
  expect(result.state.step).toBe('awaiting_mode');
  expect(api.createAptitudeTest).not.toHaveBeenCalled();
});

test('does not interpret a sentence containing A-D as an answer', async () => {
  await handleAptitudeText(active, 'can you explain this');
  expect(api.submitAptitudeAnswer).not.toHaveBeenCalled();
});

test('restart abandons the current attempt without submitting an answer', async () => {
  const result = await handleAptitudeText(active, 'start a new test');
  expect(api.abandonAptitudeTest).toHaveBeenCalledWith('session', 'test');
  expect(api.submitAptitudeAnswer).not.toHaveBeenCalled();
  expect(result.state).toEqual({ step: 'awaiting_mode', sessionToken: 'session' });
});

test('failed next-question loading cannot resubmit the saved answer', async () => {
  jest.mocked(api.submitAptitudeAnswer).mockResolvedValue({ complete: false, is_correct: true, correct_answer: 'A', explanation: 'Correct' } as Awaited<ReturnType<typeof api.submitAptitudeAnswer>>);
  jest.mocked(api.getAptitudeQuestion).mockRejectedValue(new Error('offline'));
  const result = await handleAptitudeText(active, 'A');
  expect(result.state.step).toBe('awaiting_next_question');
  expect(result.state.question).toBeUndefined();
  await handleAptitudeText(result.state, 'A');
  expect(api.submitAptitudeAnswer).toHaveBeenCalledTimes(1);
});

test('hint failure preserves the active question and shows a retryable message', async () => {
  jest.mocked(api.requestAptitudeHint).mockRejectedValueOnce(new Error('provider unavailable'));
  const result = await handleAptitudeText(active, 'hint');
  expect(result.state).toBe(active);
  expect(result.state.question).toBe(question);
  expect(result.messages[0].text).toContain('could not generate a safe hint');
  expect(result.messages[0].options).toBeDefined();
});

test('token interruption exposes Continue Test and resume restores the server question timer', async () => {
  jest.mocked(api.submitAptitudeAnswer).mockRejectedValueOnce(new Error('Insufficient token balance. Please top up to continue.'));
  const interrupted = await handleAptitudeText(active, 'A');
  expect(interrupted.state.tokenInterrupted).toBe(true);
  expect(interrupted.state.question).toBe(question);
  expect(interrupted.messages[0].options).toEqual([{ label: 'Continue Test', value: 'continue test' }]);

  const resumedQuestion = { ...question, remaining_seconds: 32 };
  jest.mocked(api.getAptitudeQuestion).mockResolvedValueOnce(resumedQuestion);
  const resumed = await handleAptitudeText(interrupted.state, 'continue test');
  expect(api.getAptitudeQuestion).toHaveBeenCalledWith('session', 'test');
  expect(resumed.state.tokenInterrupted).toBe(false);
  expect(resumed.state.question?.remaining_seconds).toBe(32);
  expect(resumed.state.step).toBe('awaiting_question');
});

test('token interruption during a hint also preserves the current question', async () => {
  jest.mocked(api.requestAptitudeHint).mockRejectedValueOnce(new Error('Insufficient token balance'));
  const interrupted = await handleAptitudeText(active, 'hint');
  expect(interrupted.state.tokenInterrupted).toBe(true);
  expect(interrupted.state.question).toBe(question);
});

test.each([
  ['category_practice', 'unanswered'],
  ['mixed', 'answered'],
  ['mixed', 'unanswered'],
] as const)('%s exit ends a %s question without submitting or scoring it', async (mode, status) => {
  jest.mocked(api.abandonAptitudeTest).mockResolvedValueOnce({ test_id: 'test', status: 'abandoned', abandoned: true });
  const result = await handleAptitudeText({ ...active, mode, question: { ...question, status, visited: true } }, 'exit test');
  expect(api.abandonAptitudeTest).toHaveBeenCalledWith('session', 'test');
  expect(api.submitAptitudeAnswer).not.toHaveBeenCalled();
  expect(api.getAptitudeResults).not.toHaveBeenCalled();
  expect(result.state).toEqual({ step: 'awaiting_mode', sessionToken: 'session' });
  expect(result.messages[0].options).toHaveLength(2);
});

test('exit also works when an active question is interrupted for tokens', async () => {
  jest.mocked(api.abandonAptitudeTest).mockResolvedValueOnce({ test_id: 'test', status: 'abandoned', abandoned: true });
  const result = await handleAptitudeText({ ...active, tokenInterrupted: true }, 'exit test');
  expect(result.state.step).toBe('awaiting_mode');
});

test('a failed backend exit leaves the attempt active', async () => {
  jest.mocked(api.abandonAptitudeTest).mockRejectedValueOnce(new Error('The assessment time has expired'));
  const result = await handleAptitudeText(active, 'exit test');
  expect(result.state).toBe(active);
  expect(result.messages[0].text).toContain('The assessment time has expired');
});

test('skip preserves the attempt and opens the next stored question', async () => {
  const next = { ...question, sequence: 2, status: 'unanswered' as const, remaining_seconds: 60 };
  jest.mocked(api.skipAptitudeQuestion).mockResolvedValueOnce(next);
  const result = await handleAptitudeText(active, 'skip question');
  expect(api.skipAptitudeQuestion).toHaveBeenCalledWith('session', 'test');
  expect(result.state.question?.sequence).toBe(2);
  expect(result.messages[0].text).toContain('skipped');
});

test('question navigation retrieves an existing stored question by sequence', async () => {
  const target = { ...question, sequence: 3, status: 'unanswered' as const };
  jest.mocked(api.getAptitudeQuestion).mockResolvedValueOnce(target);
  const result = await handleAptitudeText(active, '__aptitude_nav:3');
  expect(api.getAptitudeQuestion).toHaveBeenCalledWith('session', 'test', 3);
  expect(result.state.question?.sequence).toBe(3);
});
