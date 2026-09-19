jest.mock('../../src/lib/mockInterviewApi', () => ({
  ensureMockInterviewSession: jest.fn(),
  startMockInterview: jest.fn(),
  submitMockInterviewAnswer: jest.fn(),
  endMockInterview: jest.fn(),
  exitMockInterview: jest.fn(),
}));

import * as api from '../../src/lib/mockInterviewApi';
import { createInitialMockInterviewState, handleMockInterviewText, openMockInterviewChat, type MockInterviewFlowState } from '../../src/lib/mockInterviewFlow';

const user = { id: 'u1', name: 'Asha Rao', email: 'asha@example.com', mobile: '', initial: 'A' };
const mocked = api as jest.Mocked<typeof api>;
const withSession = (extra: Partial<MockInterviewFlowState> = {}): MockInterviewFlowState => ({ ...createInitialMockInterviewState(), sessionToken: 'token', ...extra });

test('opening the chat creates a session and offers both rounds', async () => {
  mocked.ensureMockInterviewSession.mockResolvedValue({ sessionToken: 'token', student_id: 1 });
  const { state, messages } = await openMockInterviewChat(user);
  expect(mocked.ensureMockInterviewSession).toHaveBeenCalledWith('u1', 'Asha Rao', 'asha@example.com');
  expect(state.sessionToken).toBe('token');
  expect(messages[0].options?.map((o) => o.value)).toEqual(['technical', 'hr']);
});

test('a failed session surfaces a retry option instead of throwing', async () => {
  mocked.ensureMockInterviewSession.mockRejectedValue(new Error('Agent unavailable'));
  const { state, messages } = await openMockInterviewChat(user);
  expect(state.step).toBe('error');
  expect(messages[0].text).toContain('Agent unavailable');
  expect(messages[0].options?.[0].value).toBe('retry');
});

test('a technical round asks for a topic, then a difficulty, then starts', async () => {
  let result = await handleMockInterviewText(withSession(), user, 'technical');
  expect(result.state.step).toBe('awaiting_subject');
  result = await handleMockInterviewText(result.state, user, 'Python');
  expect(result.state).toMatchObject({ step: 'choose_difficulty', subject: 'Python' });

  mocked.startMockInterview.mockResolvedValue({ interview_id: 9, question_order: 1, question: 'What is a list?', total_questions: 5 });
  result = await handleMockInterviewText(result.state, user, 'beginner');
  expect(mocked.startMockInterview).toHaveBeenCalledWith('token', { round_type: 'technical', subject: 'Python', difficulty: 'beginner' });
  expect(result.state).toMatchObject({ step: 'in_interview', interviewId: 9, questionOrder: 1 });
  expect(result.messages[1].text).toContain('What is a list?');
});

test('an HR round skips the topic step', async () => {
  const result = await handleMockInterviewText(withSession(), user, 'hr');
  expect(result.state.step).toBe('choose_difficulty');
});

test('answers advance to the next question and finish with a score', async () => {
  const inInterview = withSession({ step: 'in_interview', interviewId: 9, questionOrder: 1, totalQuestions: 2 });
  mocked.submitMockInterviewAnswer.mockResolvedValueOnce({ done: false, verdict: 'Good', question: 'Second?', question_order: 2, total_questions: 2 });
  let result = await handleMockInterviewText(inInterview, user, 'my answer');
  expect(mocked.submitMockInterviewAnswer).toHaveBeenCalledWith('token', 9, 1, 'my answer');
  expect(result.state.questionOrder).toBe(2);
  expect(result.messages[0].text).toContain('Good');

  mocked.submitMockInterviewAnswer.mockResolvedValueOnce({ done: true, verdict: 'Fine' });
  mocked.endMockInterview.mockResolvedValue({ total_marks: 7, max_marks: 10 });
  result = await handleMockInterviewText(result.state, user, 'last answer');
  expect(result.state.step).toBe('completed');
  expect(result.messages.map((m) => m.text).join('\n')).toContain('Score: 7 / 10');
});

test('exiting calls the agent and ends the flow', async () => {
  mocked.exitMockInterview.mockResolvedValue({});
  const result = await handleMockInterviewText(withSession({ step: 'in_interview', interviewId: 9, questionOrder: 3 }), user, 'exit_interview');
  expect(mocked.exitMockInterview).toHaveBeenCalledWith('token', 9, 3);
  expect(result.state.step).toBe('completed');
});

test('without a session token the flow reopens instead of calling the agent blindly', async () => {
  mocked.ensureMockInterviewSession.mockResolvedValue({ sessionToken: 'fresh', student_id: 1 });
  const result = await handleMockInterviewText(createInitialMockInterviewState(), user, 'technical');
  expect(result.state.sessionToken).toBe('fresh');
  expect(mocked.startMockInterview).not.toHaveBeenCalled();
});
