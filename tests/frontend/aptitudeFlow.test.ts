jest.mock('../../src/lib/aptitudeApi', () => ({
  abandonAptitudeTest: jest.fn(), createAptitudeTest: jest.fn(),
  ensureAptitudeSession: jest.fn(), getAptitudeQuestion: jest.fn(),
  getAptitudeResults: jest.fn(), requestAptitudeHint: jest.fn(),
  submitAptitudeAnswer: jest.fn(), downloadAptitudeReport: jest.fn(),
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
