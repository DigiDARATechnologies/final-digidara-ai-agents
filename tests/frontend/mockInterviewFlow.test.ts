jest.mock('../../src/lib/mockInterviewApi', () => ({
  ensureMockInterviewSession: jest.fn(),
  getActiveMockInterview: jest.fn(),
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
  mocked.getActiveMockInterview.mockResolvedValue({ active: false });
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

test('a technical custom-topic round asks for a topic, then a difficulty, then starts ten questions', async () => {
  let result = await handleMockInterviewText(withSession(), user, 'technical');
  expect(result.state.step).toBe('choose_mode');
  result = await handleMockInterviewText(result.state, user, 'custom_topic');
  expect(result.state.step).toBe('awaiting_subject');
  result = await handleMockInterviewText(result.state, user, 'Python');
  expect(result.state).toMatchObject({ step: 'choose_difficulty', subject: 'Python' });

  mocked.startMockInterview.mockResolvedValue({ interview_id: 9, question_order: 1, question: 'What is a list?', total_questions: 10 });
  result = await handleMockInterviewText(result.state, user, 'beginner');
  expect(result.state.step).toBe('choose_question_count');
  result = await handleMockInterviewText(result.state, user, '10');
  expect(mocked.startMockInterview).toHaveBeenCalledWith('token', { round_type: 'technical', interview_mode: 'custom_topic', subject: 'Python', difficulty: 'beginner', num_questions: 10 });
  expect(result.state).toMatchObject({ step: 'in_interview', interviewId: 9, questionOrder: 1 });
  expect(result.messages[1].text).toContain('What is a list?');
});

test('opening the chat resumes an existing interview with its original difficulty', async () => {
  mocked.ensureMockInterviewSession.mockResolvedValue({ sessionToken: 'token', student_id: 1 });
  mocked.getActiveMockInterview.mockResolvedValue({ active: true, interview_id: 19, question_order: 3, real_question_index: 3, question: 'Describe an index.', total_questions: 10, difficulty: 'advanced', round_type: 'technical', interview_mode: 'role', role_name: 'Data Analyst' });
  const { state, messages } = await openMockInterviewChat(user);
  expect(state).toMatchObject({ step: 'in_interview', interviewId: 19, difficulty: 'advanced', questionOrder: 3, roleName: 'Data Analyst' });
  expect(messages[1].text).toContain('Describe an index.');
});

test('a technical role round sends the selected role to the backend', async () => {
  let result = await handleMockInterviewText(withSession(), user, 'technical');
  result = await handleMockInterviewText(result.state, user, 'role');
  expect(result.state.step).toBe('choose_role');
  result = await handleMockInterviewText(result.state, user, 'AI Engineer');
  expect(result.state.roleName).toBe('AI Engineer');
  mocked.startMockInterview.mockResolvedValue({ interview_id: 10, question_order: 1, question: 'What is retrieval?', total_questions: 10 });
  result = await handleMockInterviewText(result.state, user, 'intermediate');
  await handleMockInterviewText(result.state, user, '10');
  expect(mocked.startMockInterview).toHaveBeenCalledWith('token', { round_type: 'technical', interview_mode: 'role', role_name: 'AI Engineer', difficulty: 'intermediate', num_questions: 10 });
});

test('an HR round skips the topic step', async () => {
  const result = await handleMockInterviewText(withSession(), user, 'hr');
  expect(result.state.step).toBe('choose_difficulty');
  mocked.startMockInterview.mockResolvedValue({ interview_id: 11, question_order: 1, question: 'Tell me about yourself.', total_questions: 10 });
  let next = await handleMockInterviewText(result.state, user, 'advanced');
  await handleMockInterviewText(next.state, user, '10');
  expect(mocked.startMockInterview).toHaveBeenCalledWith('token', { round_type: 'hr', interview_mode: 'course', subject: undefined, difficulty: 'advanced', num_questions: 10 });
});

test('answers advance with their timing and finish with the four scores and scorecard', async () => {
  const inInterview = withSession({ step: 'in_interview', interviewId: 9, questionOrder: 1, totalQuestions: 2 });
  mocked.submitMockInterviewAnswer.mockResolvedValueOnce({ done: false, verdict: 'Good', question: 'Second?', question_order: 2, total_questions: 2 });
  let result = await handleMockInterviewText(inInterview, user, 'my answer', { timeTakenSec: 25 });
  expect(mocked.submitMockInterviewAnswer).toHaveBeenCalledWith('token', 9, 1, 'my answer', 25, undefined);
  expect(result.state.questionOrder).toBe(2);
  expect(result.messages[0].text).toBe('Answer saved. Detailed feedback will appear in your final report.');

  mocked.submitMockInterviewAnswer.mockResolvedValueOnce({ done: true, verdict: 'Fine' });
  mocked.endMockInterview.mockResolvedValue({ interview_id: 9, total_marks: 7, max_marks: 10, overall_score: 8, technical_accuracy: 7, communication_clarity: 9, confidence: 8, scorecard: [{ question_number: 1, verdict: 'correct', verdict_reason: 'Clear answer' }] });
  result = await handleMockInterviewText(result.state, user, 'last answer');
  expect(result.state.step).toBe('completed');
  expect(result.state.summary).toMatchObject({ overall_score: 8, technical_accuracy: 7, communication_clarity: 9, confidence: 8 });
  expect(result.state.summary?.scorecard?.[0].verdict_reason).toBe('Clear answer');
});

test('an expired unanswered question is submitted as a timeout', async () => {
  mocked.submitMockInterviewAnswer.mockResolvedValue({ done: false, question: 'Next?', question_order: 2, total_questions: 10 });
  await handleMockInterviewText(withSession({ step: 'in_interview', interviewId: 9, questionOrder: 1 }), user, '', { timeTakenSec: 60, timedOut: true });
  expect(mocked.submitMockInterviewAnswer).toHaveBeenCalledWith('token', 9, 1, '', 60, true);
});

test('exiting calls the agent and ends the flow', async () => {
  mocked.exitMockInterview.mockResolvedValue({});
  const result = await handleMockInterviewText(withSession({ step: 'in_interview', interviewId: 9, questionOrder: 3 }), user, 'exit_interview');
  expect(mocked.exitMockInterview).toHaveBeenCalledWith('token', 9, 3);
  expect(result.state.step).toBe('completed');
});

test('without a session token the flow reopens instead of calling the agent blindly', async () => {
  mocked.ensureMockInterviewSession.mockResolvedValue({ sessionToken: 'fresh', student_id: 1 });
  mocked.getActiveMockInterview.mockResolvedValue({ active: false });
  const result = await handleMockInterviewText(createInitialMockInterviewState(), user, 'technical');
  expect(result.state.sessionToken).toBe('fresh');
  expect(mocked.startMockInterview).not.toHaveBeenCalled();
});
