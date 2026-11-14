jest.mock('../../src/lib/mockInterviewApi', () => ({
  ensureMockInterviewSession: jest.fn(),
  getActiveMockInterview: jest.fn(),
  startMockInterview: jest.fn(),
  submitMockInterviewAnswer: jest.fn(),
  endMockInterview: jest.fn(),
  exitMockInterview: jest.fn(),
}));

import * as api from '../../src/lib/mockInterviewApi';
import { setLearnerContext } from '../../src/lib/learnerContext';
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

test('a technical custom-topic round asks for a topic, then starts at the learner level with no difficulty step', async () => {
  let result = await handleMockInterviewText(withSession(), user, 'technical');
  expect(result.state.step).toBe('choose_mode');
  result = await handleMockInterviewText(result.state, user, 'custom_topic');
  expect(result.state.step).toBe('awaiting_subject');
  result = await handleMockInterviewText(result.state, user, 'Python');
  expect(result.state).toMatchObject({ step: 'choose_question_count', subject: 'Python', difficulty: 'beginner' });

  mocked.startMockInterview.mockResolvedValue({ interview_id: 9, question_order: 1, question: 'What is a list?', total_questions: 10 });
  result = await handleMockInterviewText(result.state, user, '10');
  expect(mocked.startMockInterview).toHaveBeenCalledWith('token', { round_type: 'technical', interview_mode: 'custom_topic', subject: 'Python', difficulty: 'beginner', num_questions: 10 });
  expect(result.state).toMatchObject({ step: 'in_interview', interviewId: 9, questionOrder: 1 });
  expect(result.messages[1].text).toContain('What is a list?');
});

test('starting a new interview while a finished one waits for its report shows that report, not its last question', async () => {
  let result = await handleMockInterviewText(withSession(), user, 'technical');
  result = await handleMockInterviewText(result.state, user, 'custom_topic');
  result = await handleMockInterviewText(result.state, user, 'Excel');
  mocked.startMockInterview.mockResolvedValue({ interview_id: 30, question_order: 15, question: 'How would you troubleshoot an Excel dashboard?', total_questions: 15, resumed_existing: true, awaiting_report: true });
  mocked.endMockInterview.mockResolvedValue({ total_marks: 10, max_marks: 15, scorecard: [] } as never);
  result = await handleMockInterviewText(result.state, user, '5');
  expect(mocked.endMockInterview).toHaveBeenCalledWith('token', 30);
  expect(result.state.step).toBe('completed');
  expect(result.messages.map((m) => m.text).join(' ')).not.toContain('How would you troubleshoot');
  expect(result.messages[0].text).toContain('previous interview was finished');
});

test('a report that cannot be made still offers a way out of the interview', async () => {
  let result = await handleMockInterviewText(withSession(), user, 'technical');
  result = await handleMockInterviewText(result.state, user, 'custom_topic');
  result = await handleMockInterviewText(result.state, user, 'Excel');
  mocked.startMockInterview.mockResolvedValue({ interview_id: 31, question_order: 3, question: 'Q3', total_questions: 5, resumed_existing: true, awaiting_report: true });
  mocked.endMockInterview.mockRejectedValue(new Error('This interview is not ready to complete.'));
  // Closing it failed too, so the learner is offered the way out.
  mocked.exitMockInterview.mockRejectedValueOnce(new Error('offline'));
  result = await handleMockInterviewText(result.state, user, '5');
  expect(result.state.step).toBe('in_interview');
  expect(result.messages[result.messages.length - 1].options?.map((o) => o.value)).toEqual(['retry_report', 'exit_interview']);
});

test('a resumed interview whose next question was just issued continues with it', async () => {
  let result = await handleMockInterviewText(withSession(), user, 'technical');
  result = await handleMockInterviewText(result.state, user, 'custom_topic');
  result = await handleMockInterviewText(result.state, user, 'Excel');
  mocked.endMockInterview.mockClear();
  mocked.startMockInterview.mockResolvedValue({ interview_id: 32, question_order: 4, real_question_index: 4, question: 'What is a pivot table?', total_questions: 5, resumed_existing: true, awaiting_report: false });
  result = await handleMockInterviewText(result.state, user, '5');
  expect(mocked.endMockInterview).not.toHaveBeenCalled();
  expect(result.state).toMatchObject({ step: 'in_interview', interviewId: 32, questionOrder: 4 });
  expect(result.messages[1].text).toContain('What is a pivot table?');
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
  expect(result.state.step).toBe('choose_question_count');
  await handleMockInterviewText(result.state, user, '10');
  expect(mocked.startMockInterview).toHaveBeenCalledWith('token', { round_type: 'technical', interview_mode: 'role', role_name: 'AI Engineer', difficulty: 'beginner', num_questions: 10 });
});

test('an HR round skips the topic step', async () => {
  const result = await handleMockInterviewText(withSession(), user, 'hr');
  expect(result.state.step).toBe('choose_question_count');
  mocked.startMockInterview.mockResolvedValue({ interview_id: 11, question_order: 1, question: 'Tell me about yourself.', total_questions: 10 });
  await handleMockInterviewText(result.state, user, '10');
  expect(mocked.startMockInterview).toHaveBeenCalledWith('token', { round_type: 'hr', interview_mode: 'course', subject: undefined, difficulty: 'beginner', num_questions: 10 });
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
  const result = await handleMockInterviewText(withSession({ step: 'in_interview', interviewId: 9, questionOrder: 1 }), user, '', { timeTakenSec: 60, timedOut: true });
  expect(mocked.submitMockInterviewAnswer).toHaveBeenCalledWith('token', 9, 1, '', 60, true);
  expect(result.messages[0].text).toBe('Time expired - no answer submitted.');
});

test('exiting calls the agent and ends the flow', async () => {
  mocked.exitMockInterview.mockResolvedValue({});
  const result = await handleMockInterviewText(withSession({ step: 'in_interview', interviewId: 9, questionOrder: 3 }), user, 'exit_interview');
  expect(mocked.exitMockInterview).toHaveBeenCalledWith('token', 9, 3);
  expect(result.state.step).toBe('completed');
});

test('exiting shows the score for the questions already answered', async () => {
  mocked.exitMockInterview.mockResolvedValue({
    status: 'exited', completed_question_count: 2, total_marks: 1.5, max_marks: 2,
    scorecard: [
      { question: 'What is a list?', verdict: 'correct', verdict_reason: 'Clear and accurate.' },
      { question: 'What is a dictionary used for?', verdict: 'partial' },
    ],
  });
  const result = await handleMockInterviewText(withSession({ step: 'in_interview', interviewId: 9, questionOrder: 3, totalQuestions: 5 }), user, 'exit_interview');
  const text = result.messages[0].text;
  expect(text).toContain("You've exited the interview.");
  expect(text).toContain('Your score: 1.5 / 2');
  expect(text).toContain('2 of 5 questions answered');
  expect(text).toContain('Correct - Clear and accurate.');
  expect(text).toContain('Partly correct');
});

test('exiting before answering anything says there is no score', async () => {
  mocked.exitMockInterview.mockResolvedValue({ status: 'exited', completed_question_count: 0 });
  const result = await handleMockInterviewText(withSession({ step: 'in_interview', interviewId: 9, questionOrder: 1 }), user, 'exit_interview');
  expect(result.messages[0].text).toContain('No questions were answered');
});

test('an interview ended for silence exits the same way and says why', async () => {
  mocked.exitMockInterview.mockResolvedValue({});
  const result = await handleMockInterviewText(withSession({ step: 'in_interview', interviewId: 9, questionOrder: 3 }), user, 'exit_interview_inactive');
  expect(mocked.exitMockInterview).toHaveBeenCalledWith('token', 9, 3);
  expect(result.state.step).toBe('completed');
  expect(result.messages[0].text).toContain('no answer was heard');
  expect(result.messages[0].text).toContain('Hey, are you there?');
});

test('without a session token the flow reopens instead of calling the agent blindly', async () => {
  mocked.ensureMockInterviewSession.mockResolvedValue({ sessionToken: 'fresh', student_id: 1 });
  mocked.getActiveMockInterview.mockResolvedValue({ active: false });
  const result = await handleMockInterviewText(createInitialMockInterviewState(), user, 'technical');
  expect(result.state.sessionToken).toBe('fresh');
  expect(mocked.startMockInterview).not.toHaveBeenCalled();
});

describe('with a target role', () => {
  beforeEach(() => setLearnerContext({
    profile: { target_role: 'python developer', degree: 'B.E', skills: ['Python', 'Django', 'SQL'], experience: 'fresher',
      onboarding_completed: true, onboarding_completed_at: '2026-10-08T00:00:00' },
    levels: [{ agent_name: 'mock_interview_agent', agent_label: 'Mock Interview', level: 'hard' as never, source: 'readiness', updated_at: null }],
    level_choices: [], consent_required: false, membership: null,
  } as never));
  afterEach(() => setLearnerContext(null));

  test('every round offered comes from the target role and skills, never a level choice', async () => {
    mocked.ensureMockInterviewSession.mockResolvedValue({ sessionToken: 'token', student_id: 1 });
    mocked.getActiveMockInterview.mockResolvedValue({ active: false } as never);
    const { messages } = await openMockInterviewChat(user);
    expect(messages[0].options?.map((o) => o.label)).toEqual([
      'Technical interview for Python Developer', 'Python interview', 'Django interview', 'SQL interview', 'HR interview for Python Developer',
    ]);
    expect(JSON.stringify(messages)).not.toMatch(/Beginner|Intermediate|Advanced/);
  });

  test('a skill round runs that skill at the learner Job Readiness level', async () => {
    let result = await handleMockInterviewText(withSession(), user, 'skill:Django');
    expect(result.state).toMatchObject({ step: 'choose_question_count', subject: 'Django', interviewMode: 'custom_topic', difficulty: 'advanced' });
    mocked.startMockInterview.mockResolvedValue({ interview_id: 12, question_order: 1, question: 'What is an ORM?', total_questions: 5 });
    result = await handleMockInterviewText(result.state, user, '5');
    expect(mocked.startMockInterview).toHaveBeenCalledWith('token', { round_type: 'technical', interview_mode: 'custom_topic', subject: 'Django', difficulty: 'advanced', num_questions: 5 });
  });
});

describe('a previous interview whose report can never be made', () => {
  const resumed = { interview_id: 7, question: 'Old question', question_order: 5, total_questions: 5, resumed_existing: true, awaiting_report: true };
  const fresh = { interview_id: 8, question: 'New question', question_order: 1, total_questions: 5 };
  const choosing = { step: 'choose_question_count', sessionToken: 'token', roundType: 'technical', interviewMode: 'custom_topic', subject: 'SQL', difficulty: 'beginner' } as const;

  test('is closed, and the interview the learner asked for starts', async () => {
    jest.mocked(api.startMockInterview).mockResolvedValueOnce(resumed as never).mockResolvedValueOnce(fresh as never);
    jest.mocked(api.endMockInterview).mockRejectedValueOnce(new Error('This interview is not ready to complete. Answer all main questions or exit the interview instead.'));
    jest.mocked(api.exitMockInterview).mockResolvedValueOnce({ scorecard: [] } as never);
    const result = await handleMockInterviewText(choosing as never, user, '5');
    expect(api.exitMockInterview).toHaveBeenCalledWith('token', 7, 5);
    expect(result.state.step).toBe('in_interview');
    expect(result.state.interviewId).toBe(8);
    expect(result.messages[0].text).toContain('could not be continued');
  });

  test('never loops when the same interview keeps coming back', async () => {
    jest.mocked(api.exitMockInterview).mockClear();
    jest.mocked(api.startMockInterview).mockResolvedValue(resumed as never);
    jest.mocked(api.endMockInterview).mockRejectedValue(new Error('This interview is not ready to complete.'));
    jest.mocked(api.exitMockInterview).mockResolvedValue({ scorecard: [] } as never);
    const result = await handleMockInterviewText(choosing as never, user, '5');
    expect(api.exitMockInterview).toHaveBeenCalledTimes(1);
    expect(result.state.step).toBe('in_interview');
    jest.mocked(api.startMockInterview).mockReset();
    jest.mocked(api.endMockInterview).mockReset();
  });

  test('a report that is only delayed is not closed', async () => {
    jest.mocked(api.exitMockInterview).mockClear();
    jest.mocked(api.startMockInterview).mockResolvedValueOnce(resumed as never);
    jest.mocked(api.endMockInterview).mockRejectedValueOnce(new Error('Interview evaluation is temporarily unavailable.'));
    const result = await handleMockInterviewText(choosing as never, user, '5');
    expect(api.exitMockInterview).not.toHaveBeenCalled();
    expect(result.messages.map((m) => m.text).join(' ')).toContain('still processing');
  });
});

test('one failed save is sent again by itself and the next question follows', async () => {
  const live = { step: 'in_interview', sessionToken: 'token', interviewId: 9, question: 'Q1', questionOrder: 1, realQuestionIndex: 1, totalQuestions: 5 } as MockInterviewFlowState;
  jest.mocked(api.submitMockInterviewAnswer)
    .mockReset()
    .mockRejectedValueOnce(new Error('502'))
    .mockResolvedValueOnce({ question: 'Q2', question_order: 2, real_question_index: 2, total_questions: 5 } as never);
  const result = await handleMockInterviewText(live, user, 'My answer');
  expect(api.submitMockInterviewAnswer).toHaveBeenCalledTimes(2);
  expect(result.state.question).toBe('Q2');
});

test('Retry on a report that can never be made closes the interview instead of failing again', async () => {
  jest.mocked(api.endMockInterview).mockReset().mockRejectedValue(new Error('This interview is not ready to complete.'));
  jest.mocked(api.exitMockInterview).mockReset().mockResolvedValue({ scorecard: [] } as never);
  const stuck = { step: 'in_interview', sessionToken: 't', interviewId: 7, questionOrder: 5, totalQuestions: 5 } as MockInterviewFlowState;
  const result = await handleMockInterviewText(stuck, user, 'retry_report');
  expect(api.exitMockInterview).toHaveBeenCalledWith('t', 7, 5);
  expect(result.state.step).toBe('completed');
  expect(result.messages[0].text).toContain('could not be continued');
  jest.mocked(api.endMockInterview).mockReset();
});

test('a provisional scorecard remains visible and retry completes the full report', async () => {
  const state = {
    step: 'in_interview', sessionToken: 'token', interviewId: 31,
    question: undefined, questionOrder: 5, totalQuestions: 5,
  } as MockInterviewFlowState;
  jest.mocked(api.endMockInterview).mockReset().mockResolvedValueOnce({
    interview_id: 31, provisional: true, report_status: 'provisional', retryable: true,
    report_message: 'Saved answers are ready; detailed evaluation is pending.',
    overall_score: 6, total_marks: 3, max_marks: 5,
  } as never).mockResolvedValueOnce({
    interview_id: 31, overall_score: 7, total_marks: 4, max_marks: 5,
  } as never);

  const provisional = await handleMockInterviewText(state, user, 'retry_report');
  expect(provisional.state.step).toBe('report_pending');
  expect(provisional.state.summary?.provisional).toBe(true);
  expect(provisional.messages[0].options).toEqual([
    { label: 'Retry full report', value: 'retry_report' },
  ]);

  const completed = await handleMockInterviewText(provisional.state, user, 'retry_report');
  expect(completed.state.step).toBe('completed');
  expect(completed.state.summary?.overall_score).toBe(7);
  expect(api.endMockInterview).toHaveBeenCalledTimes(2);
  expect(api.exitMockInterview).not.toHaveBeenCalled();
});

test('a failed full-report retry keeps the provisional scorecard available', async () => {
  const pending = {
    step: 'report_pending', sessionToken: 'token', interviewId: 32,
    summary: { interview_id: 32, provisional: true, report_status: 'provisional', overall_score: 4 },
  } as MockInterviewFlowState;
  jest.mocked(api.endMockInterview).mockReset().mockRejectedValueOnce(new Error('provider timeout'));

  const result = await handleMockInterviewText(pending, user, 'retry_report');
  expect(result.state.step).toBe('report_pending');
  expect(result.state.summary).toEqual(pending.summary);
  expect(result.messages[0].options).toEqual([
    { label: 'Retry full report', value: 'retry_report' },
  ]);
});
