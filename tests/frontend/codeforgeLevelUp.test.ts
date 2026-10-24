jest.mock('../../src/lib/codeforgeApi', () => ({
  submitProblem: jest.fn(),
  submitMcqAnswer: jest.fn(),
  runProblem: jest.fn(),
  askTutor: jest.fn(),
  getProblem: jest.fn(),
  listLevelProblems: jest.fn(),
}));
jest.mock('../../src/lib/learnerApi', () => ({
  fetchReadiness: jest.fn(),
  fetchLearnerSummary: jest.fn(),
}));

import { handleCodeForgeText, submitCodeForgeCode, type CodeForgeFlowState } from '../../src/lib/codeforgeFlow';
import * as api from '../../src/lib/codeforgeApi';
import * as learnerApi from '../../src/lib/learnerApi';
import { learnerLevel, setLearnerContext } from '../../src/lib/learnerContext';

const mocked = jest.mocked(api);
const learner = jest.mocked(learnerApi);

const summaryAt = (level: string) => ({ profile: {}, levels: [{ agent_name: 'codeforge_agent', level }] }) as never;

function problem(slug: string, difficulty: 'Easy' | 'Medium' | 'Hard', progress: string) {
  return { id: slug.length, name: slug, slug, description: '', difficulty, language: 'python', question_type: 'code' as const,
    max_score: 100, progress, best_score: 0, attempts: 0, sequence: 1 };
}

function solving(problems: ReturnType<typeof problem>[], current: string): CodeForgeFlowState {
  return { step: 'awaiting_code', sessionToken: 't', courses: [], technologies: [], topics: [], problems,
    courseSlug: 'python-full-stack', technologySlug: 'python', technologyName: 'Python', problemSlug: current, problemId: 7 };
}

const accepted = { status: 'Accepted', mode: 'submit', score: 100, passedTests: 2, totalTests: 2, tests: [], submissionId: 9 } as never;

beforeEach(() => {
  jest.clearAllMocks();
  setLearnerContext(summaryAt('medium'));
  mocked.submitProblem.mockResolvedValue(accepted);
  learner.fetchReadiness.mockResolvedValue({} as never);
});

test('solving the last Medium problem unlocks Hard at once, without a reload', async () => {
  learner.fetchLearnerSummary.mockResolvedValue(summaryAt('hard'));
  const state = solving([problem('easy-1', 'Easy', 'Solved'), problem('med-1', 'Medium', 'Solved'), problem('med-2', 'Medium', 'Attempted')], 'med-2');

  const { messages } = await submitCodeForgeCode(state, 'print(1)');

  expect(learner.fetchReadiness).toHaveBeenCalledWith(true);
  expect(learnerLevel('codeforge_agent')).toBe('hard');
  expect(messages.at(-1)?.text).toContain('Medium level complete! Hard problems are unlocked now.');
  expect(messages.at(-1)?.options?.map((o) => o.value)).toEqual(['choose_another_problem', '__problemset__']);
});

test('a Medium problem solved while others are left does not ask the platform', async () => {
  const state = solving([problem('med-1', 'Medium', 'Not Started'), problem('med-2', 'Medium', 'Attempted')], 'med-2');

  const { messages } = await submitCodeForgeCode(state, 'print(1)');

  expect(learner.fetchReadiness).not.toHaveBeenCalled();
  expect(messages).toHaveLength(1);
  expect(messages[0].options?.[0].label).toBe('Next problem: med-1');
});

test('when the platform has not moved the learner up, nothing extra is said', async () => {
  learner.fetchLearnerSummary.mockResolvedValue(summaryAt('medium'));
  const state = solving([problem('med-1', 'Medium', 'Attempted')], 'med-1');

  const { messages } = await submitCodeForgeCode(state, 'print(1)');

  expect(learner.fetchReadiness).toHaveBeenCalled();
  expect(messages).toHaveLength(1);
});

test('opening a technology whose level is already finished moves straight to the next level', async () => {
  learner.fetchLearnerSummary.mockResolvedValue(summaryAt('hard'));
  mocked.listLevelProblems
    .mockResolvedValueOnce({ problems: [problem('med-1', 'Medium', 'Solved')] } as never)
    .mockResolvedValueOnce({ problems: [problem('hard-1', 'Hard', 'Not Started')] } as never);
  const state = { ...solving([], ''), step: 'awaiting_problem' as const };

  const { messages, state: next } = await handleCodeForgeText({ ...state, step: 'awaiting_problem' }, 'choose_another_problem');

  expect(messages[0].text).toContain('Medium level complete! Hard problems are unlocked now.');
  expect(mocked.listLevelProblems).toHaveBeenLastCalledWith('t', 'python-full-stack', 'python', 'hard');
  expect(next.problems.map((p) => p.slug)).toEqual(['hard-1']);
});

test('the problem list opens on the course recommended for the learner goal', async () => {
  const { problemListCourse } = await import('../../src/lib/codeforgeFlow');
  setLearnerContext({ profile: { onboarding_completed: true, target_role: 'ai engineer', degree: 'm.sc', skills: ['python', 'llm'], experience: 'fresher' }, levels: [] } as never);
  const courses = [
    { slug: 'python-full-stack', name: 'Python Full Stack Development', description: 'Backend, database, and browser technologies.' },
    { slug: 'ai-machine-learning', name: 'AI and Machine Learning', description: 'Python and numerical foundations used in machine learning.' },
  ] as never;
  expect(problemListCourse({ courses })).toBe('ai-machine-learning');
  expect(problemListCourse({ courses, courseSlug: 'data-science' })).toBe('data-science');
});
