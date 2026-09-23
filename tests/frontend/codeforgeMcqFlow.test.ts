jest.mock('../../src/lib/codeforgeApi', () => ({
  getProblem: jest.fn(),
  submitMcqAnswer: jest.fn(),
  runProblem: jest.fn(),
  submitProblem: jest.fn(),
  askTutor: jest.fn(),
  ensureSession: jest.fn(),
  listCourses: jest.fn(),
  listTechnologies: jest.fn(),
  listTopics: jest.fn(),
  listProblems: jest.fn(),
}));

import { handleCodeForgeText, type CodeForgeFlowState } from '../../src/lib/codeforgeFlow';
import * as api from '../../src/lib/codeforgeApi';

const mocked = jest.mocked(api);

const MCQ_PROBLEM = {
  id: 1, name: 'Semantic Headings', slug: 'semantic-headings', description: 'Which tag is a top-level heading?',
  difficulty: 'Easy' as const, language: 'html', question_type: 'mcq' as const, max_score: 100,
  progress: 'Not Started', best_score: 0, attempts: 0, sequence: 1,
  options: { A: '<h1>', B: '<div>', C: '<span>', D: '<p>' },
};

const CODE_PROBLEM = {
  id: 2, name: 'Reverse a String', slug: 'reverse-a-string', description: 'Reverse it.',
  difficulty: 'Easy' as const, language: 'python', question_type: 'code' as const, max_score: 100,
  progress: 'Not Started', best_score: 0, attempts: 0, sequence: 1,
  input_format: 'text', output_format: 'reversed text', constraints: 'None.', examples: [],
  starter_code: '# write here', judge0_language_id: 71, public_tests: [],
};

function baseState(problem: typeof MCQ_PROBLEM | typeof CODE_PROBLEM): CodeForgeFlowState {
  return {
    step: 'awaiting_problem',
    sessionToken: 'session-token',
    courses: [], technologies: [], topics: [],
    problems: [{ id: problem.id, name: problem.name, slug: problem.slug, description: problem.description, difficulty: problem.difficulty, language: problem.language, question_type: problem.question_type, max_score: problem.max_score, progress: problem.progress, best_score: problem.best_score, attempts: problem.attempts, sequence: problem.sequence }],
    courseSlug: 'python-full-stack', technologySlug: 'html', topicSlug: 'semantic-elements',
  };
}

beforeEach(() => jest.clearAllMocks());

test('selecting an MCQ problem shows the question with clickable options, not a code editor step', async () => {
  mocked.getProblem.mockResolvedValue({ course: {} as never, technology: {} as never, topic: {} as never, problem: MCQ_PROBLEM });

  const { state, messages } = await handleCodeForgeText(baseState(MCQ_PROBLEM), MCQ_PROBLEM.slug);

  expect(state.step).toBe('awaiting_mcq_answer');
  expect(state.mcqOptions).toEqual(MCQ_PROBLEM.options);
  expect(messages[0].text).toContain('Which tag is a top-level heading?');
  expect(messages[0].options).toEqual([
    { value: 'A', label: 'A. <h1>' },
    { value: 'B', label: 'B. <div>' },
    { value: 'C', label: 'C. <span>' },
    { value: 'D', label: 'D. <p>' },
  ]);
});

test('a code problem is unaffected and still goes to awaiting_code', async () => {
  mocked.getProblem.mockResolvedValue({ course: {} as never, technology: {} as never, topic: {} as never, problem: CODE_PROBLEM });

  const { state, messages } = await handleCodeForgeText(baseState(CODE_PROBLEM), CODE_PROBLEM.slug);

  expect(state.step).toBe('awaiting_code');
  expect(state.mcqOptions).toBeUndefined();
  expect(messages[0].text).toContain('Write your python solution below');
});

test('choosing a correct option submits it and shows positive feedback with next-step options', async () => {
  mocked.submitMcqAnswer.mockResolvedValue({ submissionId: 1, mode: 'submit', status: 'Accepted', score: 100, isCorrect: true, correctKey: 'A', explanation: 'h1 is the top-level heading tag.' });
  const state: CodeForgeFlowState = { ...baseState(MCQ_PROBLEM), step: 'awaiting_mcq_answer', problemId: MCQ_PROBLEM.id, mcqOptions: MCQ_PROBLEM.options };

  const { state: next, messages } = await handleCodeForgeText(state, 'A');

  expect(mocked.submitMcqAnswer).toHaveBeenCalledWith('session-token', 1, 'A');
  expect(next.step).toBe('awaiting_problem');
  expect(messages[0].text).toContain('Correct!');
  expect(messages[0].text).toContain('h1 is the top-level heading tag.');
  expect(messages[0].options?.map((o) => o.value)).toEqual(['choose_another_problem', 'back_to_topics', 'back_to_courses']);
});

test('choosing a wrong option reveals the correct answer and its text', async () => {
  mocked.submitMcqAnswer.mockResolvedValue({ submissionId: 2, mode: 'submit', status: 'Wrong Answer', score: 0, isCorrect: false, correctKey: 'A', explanation: 'h1 is the top-level heading tag.' });
  const state: CodeForgeFlowState = { ...baseState(MCQ_PROBLEM), step: 'awaiting_mcq_answer', problemId: MCQ_PROBLEM.id, mcqOptions: MCQ_PROBLEM.options };

  const { messages } = await handleCodeForgeText(state, 'option B');

  expect(mocked.submitMcqAnswer).toHaveBeenCalledWith('session-token', 1, 'B');
  expect(messages[0].text).toContain('Not quite.');
  expect(messages[0].text).toContain('Correct answer: A. <h1>');
});

test('an unrecognized answer re-prompts with the same options and does not call the API', async () => {
  const state: CodeForgeFlowState = { ...baseState(MCQ_PROBLEM), step: 'awaiting_mcq_answer', problemId: MCQ_PROBLEM.id, mcqOptions: MCQ_PROBLEM.options };

  const { messages } = await handleCodeForgeText(state, 'Z');

  expect(mocked.submitMcqAnswer).not.toHaveBeenCalled();
  expect(messages[0].text).toBe('Pick an option from the list.');
  expect(messages[0].options).toHaveLength(4);
});
