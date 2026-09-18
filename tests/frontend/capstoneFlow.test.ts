jest.mock('../../src/lib/capstoneApi', () => ({
  askProjectQuestion: jest.fn(),
  checkEligibilityFree: jest.fn(),
  chooseTopic: jest.fn(),
  clarifyTopicRequest: jest.fn(),
  confirmTimer: jest.fn(),
  getThreadStatus: jest.fn(),
  submitVivaAnswer: jest.fn(),
  uploadSubmission: jest.fn(),
}));
import { handleCapstoneText, type CapstoneFlowState } from '../../src/lib/capstoneFlow';
import * as api from '../../src/lib/capstoneApi';

const vivaState: CapstoneFlowState = {
  step: 'awaiting_viva_answer',
  name: 'Learner', email: 'learner@example.test', phone: '', difficulty: 'easy',
  threadId: 'thread', vivaSubmissionId: 'submission', vivaQuestionId: 1,
  vivaQuestionText: 'Why did you choose localStorage?', vivaProgress: '2 of 10',
};

const submissionState: CapstoneFlowState = {
  step: 'awaiting_submission',
  name: 'Learner', email: 'learner@example.test', phone: '', difficulty: 'easy',
  threadId: 'thread',
};

const timerConfirmState: CapstoneFlowState = {
  step: 'awaiting_timer_confirm',
  name: 'Learner', email: 'learner@example.test', phone: '', difficulty: 'easy',
  threadId: 'thread',
};

afterEach(() => jest.clearAllMocks());

describe('mid-viva question/dispute detection', () => {
  test('a genuine question is answered via the Q&A agent, not submitted as the viva answer', async () => {
    jest.mocked(api.askProjectQuestion).mockResolvedValue({ answer: 'localStorage keeps data between sessions.', tools_used: [] });
    const result = await handleCapstoneText(vivaState, 'why did you say localStorage?');
    expect(api.askProjectQuestion).toHaveBeenCalledWith('thread', 'why did you say localStorage?');
    expect(api.submitVivaAnswer).not.toHaveBeenCalled();
    expect(result.messages[0].text).toBe('localStorage keeps data between sessions.');
    expect(result.messages[1].text).toContain('Why did you choose localStorage?');
    // The viva question slot itself is untouched.
    expect(result.state.vivaQuestionId).toBe(1);
  });

  test('a message that opens with "hey" is also treated as a question, not an answer', async () => {
    jest.mocked(api.askProjectQuestion).mockResolvedValue({ answer: 'Sure, go ahead.', tools_used: [] });
    await handleCapstoneText(vivaState, 'hey i have one question about the project');
    expect(api.askProjectQuestion).toHaveBeenCalled();
    expect(api.submitVivaAnswer).not.toHaveBeenCalled();
  });

  test('a plain answer is still submitted as the literal viva answer', async () => {
    jest.mocked(api.submitVivaAnswer).mockResolvedValue({ thread_id: 'thread', status: 'pending_viva', viva_question: { id: 2, question: 'Next?' }, viva_progress: '3 of 10' });
    await handleCapstoneText(vivaState, 'Because it persists data without a backend.');
    expect(api.submitVivaAnswer).toHaveBeenCalledWith('submission', 1, 'Because it persists data without a backend.');
    expect(api.askProjectQuestion).not.toHaveBeenCalled();
  });

  test('if the Q&A call itself fails, the text still gets submitted as the viva answer rather than silently dropped', async () => {
    jest.mocked(api.askProjectQuestion).mockRejectedValue(new Error('offline'));
    jest.mocked(api.submitVivaAnswer).mockResolvedValue({ thread_id: 'thread', status: 'pending_viva', viva_question: { id: 2, question: 'Next?' }, viva_progress: '3 of 10' });
    await handleCapstoneText(vivaState, 'why does this matter?');
    expect(api.submitVivaAnswer).toHaveBeenCalledWith('submission', 1, 'why does this matter?');
  });
});

describe('mid-resubmission dispute detection', () => {
  test('disputing a revision note gets answered instead of the canned attach-files reminder', async () => {
    jest.mocked(api.askProjectQuestion).mockResolvedValue({ answer: 'Your report does have a "2. Approach" section.', tools_used: ['read_submitted_report_sections'] });
    const result = await handleCapstoneText(submissionState, 'already have the approach section');
    expect(api.askProjectQuestion).toHaveBeenCalledWith('thread', 'already have the approach section');
    expect(result.messages[0].text).toContain('Approach');
    expect(result.messages[1].text).toContain('Attach both');
  });

  test('a plain attach-related message still gets the standard reminder', async () => {
    const result = await handleCapstoneText(submissionState, 'ok');
    expect(api.askProjectQuestion).not.toHaveBeenCalled();
    expect(result.messages[0].text).toBe('Attach both your .docx report and .zip source archive using the paperclip button.');
  });
});

describe('requirements doubts before the timer is confirmed', () => {
  test('any non-confirm message is treated as a doubt and answered', async () => {
    jest.mocked(api.askProjectQuestion).mockResolvedValue({ answer: '"Must run offline" means no network calls at all.', tools_used: ['get_project_brief'] });
    const result = await handleCapstoneText(timerConfirmState, "what does 'must run offline' mean?");
    expect(api.askProjectQuestion).toHaveBeenCalledWith('thread', "what does 'must run offline' mean?");
    expect(result.messages[0].text).toContain('no network calls');
    expect(result.messages[1].text).toContain('Start the 7-day project timer');
    expect(result.state.step).toBe('awaiting_timer_confirm');
  });

  test('confirming the timer does not go through the Q&A agent', async () => {
    jest.mocked(api.confirmTimer).mockResolvedValue({ thread_id: 'thread', deadline_at: '2026-09-25T00:00:00Z', submission_guide: {} });
    await handleCapstoneText(timerConfirmState, 'confirm');
    expect(api.askProjectQuestion).not.toHaveBeenCalled();
    expect(api.confirmTimer).toHaveBeenCalledWith('thread');
  });

  test('if the Q&A call itself fails, the plain reminder is shown instead', async () => {
    jest.mocked(api.askProjectQuestion).mockRejectedValue(new Error('offline'));
    const result = await handleCapstoneText(timerConfirmState, 'what does this requirement mean?');
    expect(result.messages[0].text).toBe('Use the button when you are ready. The timer cannot be paused.');
  });
});
