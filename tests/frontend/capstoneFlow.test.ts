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
import { handleCapstoneText, mergeCapstoneFiles, submitCapstoneFiles, type CapstoneFlowState } from '../../src/lib/capstoneFlow';
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

const topicChoiceState: CapstoneFlowState = {
  step: 'awaiting_topic_choice',
  name: 'Learner', email: 'learner@example.test', phone: '', difficulty: 'easy',
  threadId: 'thread',
  topicOptions: [
    { id: 'A', title: 'CLI Log Analyzer', summary: 'Filter and summarize log files.', medium: 'local', skills_applied: ['python'] },
    { id: 'B', title: 'Weather Dashboard', summary: 'Fetch and display forecasts.', medium: 'api', skills_applied: ['python', 'rest-api'] },
  ],
};

afterEach(() => jest.clearAllMocks());

describe('resubmitting after a failed grade', () => {
  const lastVivaAnswerState: CapstoneFlowState = { ...vivaState, vivaProgress: '10 of 10' };
  const docx = new File(['d'], 'report.docx');
  const zip = new File(['z'], 'project.zip');

  test('failing the viva goes back to awaiting_submission instead of the locked "graded" step', async () => {
    jest.mocked(api.submitVivaAnswer).mockResolvedValue({
      thread_id: 'thread', status: 'needs_revision', final_score: 42, passed: false,
      feedback: 'Too few viva answers were correct.', viva_score: 3, viva_passed: false,
    } as never);
    const result = await handleCapstoneText(lastVivaAnswerState, 'my final answer');
    expect(result.state.step).toBe('awaiting_submission');
    expect(result.state.passed).toBe(false);
    expect(result.state.docxFile).toBeUndefined();
    expect(result.messages[0].text).toContain('Not passed');
    expect(result.messages[0].text).toContain('no limit on resubmitting');
  });

  test('after a failed viva the student can attach both files again and resubmit', async () => {
    jest.mocked(api.submitVivaAnswer).mockResolvedValue({
      thread_id: 'thread', status: 'needs_revision', final_score: 42, passed: false, feedback: 'Try again.',
    } as never);
    const failed = await handleCapstoneText(lastVivaAnswerState, 'my final answer');
    const merged = mergeCapstoneFiles(failed.state, [docx, zip]);
    expect(merged.state.docxFile).toBe(docx);
    expect(merged.state.zipFile).toBe(zip);
    expect(merged.messages[0].text).toContain('Both files received');
  });

  test('a low-scoring content grade also stays open for another upload', async () => {
    jest.mocked(api.uploadSubmission).mockResolvedValue({
      thread_id: 'thread', status: 'needs_revision', final_score: 12, passed: false, revision_notes: 'Needs more work.',
    } as never);
    const result = await submitCapstoneFiles({ ...submissionState, docxFile: docx, zipFile: zip });
    expect(result.state.step).toBe('awaiting_submission');
    expect(result.state.docxFile).toBeUndefined();
    expect(result.messages[0].text).toContain('attach both files again');
  });

  test('a chat already stuck in the old locked "graded" step with a failed result is reopened for upload', () => {
    const stuck: CapstoneFlowState = { ...submissionState, step: 'graded', passed: false, finalScore: 30 };
    const merged = mergeCapstoneFiles(stuck, [docx, zip]);
    expect(merged.state.step).toBe('awaiting_submission');
    expect(merged.state.zipFile).toBe(zip);
  });

  test('a genuinely passed "graded" chat stays locked', async () => {
    const passed: CapstoneFlowState = { ...submissionState, step: 'graded', passed: true, finalScore: 90 };
    const result = await handleCapstoneText(passed, 'anything');
    expect(result.state.step).toBe('graded');
    expect(mergeCapstoneFiles(passed, [docx, zip]).messages[0].text).toContain('becomes available');
  });

  test('passing the viva still finishes at the terminal graded step', async () => {
    jest.mocked(api.submitVivaAnswer).mockResolvedValue({
      thread_id: 'thread', status: 'graded', final_score: 88, passed: true, feedback: 'Great work.', viva_score: 9, viva_passed: true,
    } as never);
    const result = await handleCapstoneText(lastVivaAnswerState, 'my final answer');
    expect(result.state.step).toBe('graded');
    expect(result.messages[0].text).toContain('You passed!');
  });
});

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

  test('a plain attach-related message still gets the standard reminder if the Q&A agent has nothing else to add', async () => {
    jest.mocked(api.askProjectQuestion).mockRejectedValue(new Error('offline'));
    const result = await handleCapstoneText(submissionState, 'ok');
    expect(result.messages[0].text).toBe('Attach both your .docx report and .zip source archive using the paperclip button.');
  });

  test('any text is routed through the Q&A agent, not just messages that look question-shaped', async () => {
    jest.mocked(api.askProjectQuestion).mockResolvedValue({ answer: 'The report should cover Problem Statement, Approach, Code, and Conclusion.', tools_used: [] });
    const result = await handleCapstoneText(submissionState, "i can't understand the requirements, explain more");
    expect(api.askProjectQuestion).toHaveBeenCalledWith('thread', "i can't understand the requirements, explain more");
    expect(result.messages[0].text).toContain('Problem Statement');
    expect(result.messages[1].text).toContain('Attach both');
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

describe('off-topic small talk before any project exists', () => {
  const topicRequestState: CapstoneFlowState = {
    step: 'awaiting_topic_request',
    name: 'Learner', email: 'learner@example.test', phone: '', difficulty: 'easy',
  };

  test.each(['hi', 'hello', 'hey there', 'who is the pm', 'how are you', 'thanks', 'good morning'])(
    'a greeting/meta message (%p) gets a scoping explanation instead of being sent as a topic request',
    async (message) => {
      const result = await handleCapstoneText(topicRequestState, message);
      expect(api.clarifyTopicRequest).not.toHaveBeenCalled();
      expect(api.checkEligibilityFree).not.toHaveBeenCalled();
      expect(result.messages[0].text).toContain('Capstone Project Agent');
      expect(result.state.step).toBe('awaiting_topic_request');
    },
  );

  test('a real request that happens to end in "?" is still treated as a topic request, not small talk', async () => {
    jest.mocked(api.clarifyTopicRequest).mockResolvedValue({ ready: true, clarifying_question: null });
    jest.mocked(api.checkEligibilityFree).mockResolvedValue({ thread_id: 'thread', eligible: true, eligibility_reason: '', topic_options: [] });
    await handleCapstoneText(topicRequestState, 'can I get a python project?');
    expect(api.clarifyTopicRequest).toHaveBeenCalledWith('can I get a python project?');
  });
});

describe('combining a clarifying-question answer with the original request', () => {
  const topicRequestState: CapstoneFlowState = {
    step: 'awaiting_topic_request',
    name: 'Learner', email: 'learner@example.test', phone: '', difficulty: 'easy',
    pendingTopicSeed: 'portfolio website',
  };

  test('a non-conflicting answer is sent to the backend as an addition, not a replacement', async () => {
    jest.mocked(api.checkEligibilityFree).mockResolvedValue({ thread_id: 'thread', eligible: true, eligibility_reason: '', topic_options: [] });
    await handleCapstoneText(topicRequestState, 'python');
    const [, , , description] = jest.mocked(api.checkEligibilityFree).mock.calls[0];
    expect(description).toContain('portfolio website');
    expect(description).toContain('python');
    expect(description).not.toMatch(/if they conflict.*go with this one/i);
  });

  test('the displayed message shows both the original request and the follow-up answer, not just the answer', async () => {
    jest.mocked(api.checkEligibilityFree).mockResolvedValue({ thread_id: 'thread', eligible: true, eligibility_reason: '', topic_options: [] });
    const result = await handleCapstoneText(topicRequestState, 'python');
    expect(result.messages[0].text).toContain('portfolio website');
    expect(result.messages[0].text).toContain('python');
  });

  test('a genuinely different language/role is still framed so the newer answer can win', async () => {
    jest.mocked(api.checkEligibilityFree).mockResolvedValue({ thread_id: 'thread', eligible: true, eligibility_reason: '', topic_options: [] });
    await handleCapstoneText({ ...topicRequestState, pendingTopicSeed: 'python developer role' }, 'html developer');
    const [, , , description] = jest.mocked(api.checkEligibilityFree).mock.calls[0];
    expect(description).toContain('python developer role');
    expect(description).toContain('html developer');
    expect(description).toMatch(/different role, language, or domain/i);
  });

  test.each(['your choice', 'you decide', 'up to you', 'surprise me', 'idk', 'no preference'])(
    'a deferral answer (%p) is never appended as if it were topic content',
    async (deferral) => {
      jest.mocked(api.checkEligibilityFree).mockResolvedValue({ thread_id: 'thread', eligible: true, eligibility_reason: '', topic_options: [] });
      const result = await handleCapstoneText({ ...topicRequestState, pendingTopicSeed: 'python' }, deferral);
      const [, , , description] = jest.mocked(api.checkEligibilityFree).mock.calls[0];
      expect(description).not.toContain(deferral);
      expect(description).toContain('python');
      expect(description).toMatch(/own best judgment/i);
      expect(result.messages[0].text).not.toContain(deferral);
      expect(result.messages[0].text).toContain('python');
    },
  );
});

describe('choosing a project topic (A/B)', () => {
  test('an exact selection still works', async () => {
    jest.mocked(api.chooseTopic).mockResolvedValue({ thread_id: 'thread', requirements: {} } as never);
    const result = await handleCapstoneText(topicChoiceState, 'A');
    expect(api.chooseTopic).toHaveBeenCalledWith('thread', 'A');
    expect(result.state.step).toBe('awaiting_timer_confirm');
  });

  test('an unrelated message that merely contains the letter "a" is not silently treated as choosing option A', async () => {
    jest.mocked(api.askProjectQuestion).mockRejectedValue(new Error('offline'));
    const result = await handleCapstoneText(topicChoiceState, 'i need to change the project topics');
    expect(api.chooseTopic).not.toHaveBeenCalled();
    expect(result.state.step).toBe('awaiting_topic_choice');
  });

  test('a genuine question about the options is answered via the Q&A agent, then the choice is re-prompted', async () => {
    jest.mocked(api.askProjectQuestion).mockResolvedValue({ answer: 'Both are scoped for 7 days; B needs a public weather API key.', tools_used: [] });
    const result = await handleCapstoneText(topicChoiceState, 'does option B need an API key?');
    expect(api.askProjectQuestion).toHaveBeenCalledWith('thread', 'does option B need an API key?');
    expect(api.chooseTopic).not.toHaveBeenCalled();
    expect(result.messages[0].text).toContain('API key');
    expect(result.messages[1].text).toContain('Choose project A or B');
  });

  test('an unrelated, non-question message is still routed through the Q&A agent, not just pre-filtered by matching question-shaped text', async () => {
    jest.mocked(api.askProjectQuestion).mockResolvedValue({ answer: "I can only help with your two current project options — pick A or B to continue.", tools_used: [] });
    const result = await handleCapstoneText(topicChoiceState, 'i need to change the project topics');
    expect(api.askProjectQuestion).toHaveBeenCalledWith('thread', 'i need to change the project topics');
    expect(api.chooseTopic).not.toHaveBeenCalled();
    expect(result.messages[0].text).toContain('pick A or B');
    expect(result.messages[1].text).toContain('Choose project A or B');
  });
});

describe('example report and zip downloads', () => {
  const exampleHrefs = ['/capstone-examples/capstone-example-report.docx', '/capstone-examples/capstone-example-project.zip'];

  test('the requirements message offers the examples next to the start button', async () => {
    jest.mocked(api.chooseTopic).mockResolvedValue({ thread_id: 'thread', requirements: {} } as never);
    const result = await handleCapstoneText(
      { ...timerConfirmState, step: 'awaiting_topic_choice', topicOptions: [{ id: 'A', title: 'Tracker', summary: 's' }] } as CapstoneFlowState,
      'A',
    );
    const options = result.messages[0].options ?? [];
    expect(options[0]).toMatchObject({ value: 'confirm' });
    expect(options.filter((option) => option.href).map((option) => option.href)).toEqual(exampleHrefs);
  });

  test('the submission guide offers the examples again once the timer starts', async () => {
    jest.mocked(api.confirmTimer).mockResolvedValue({ thread_id: 'thread', deadline_at: '2026-09-25T00:00:00Z', submission_guide: {} });
    const result = await handleCapstoneText(timerConfirmState, 'confirm');
    expect(result.state.step).toBe('awaiting_submission');
    expect(result.messages[0].options?.map((option) => option.href)).toEqual(exampleHrefs);
    expect(result.messages[0].text).toContain('example report');
  });
});
