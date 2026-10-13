jest.mock('../../src/lib/codeforgeApi', () => ({
  ASSESSMENT_KIND_LABELS: { hard: 'Hard problem', expert: 'Expert problem', real_world: 'Real-world task' },
  getAssessmentProblem: jest.fn(), finishAssessment: jest.fn(), submitProblem: jest.fn(), runProblem: jest.fn(),
  askTutor: jest.fn(), ensureSession: jest.fn(), listCourses: jest.fn(), listTechnologies: jest.fn(), listLevelProblems: jest.fn(),
  getProblem: jest.fn(), submitMcqAnswer: jest.fn(),
}));

import * as api from '../../src/lib/codeforgeApi';
import { enterAssessment, handleCodeForgeText, submitCodeForgeCode, type CodeForgeFlowState } from '../../src/lib/codeforgeFlow';

const items = [
  { position: 1, kind: 'hard' as const, best_score: 0, attempts: 0, problem_id: 11, name: 'Matrix Path', slug: 'matrix-path', difficulty: 'Hard' },
  { position: 2, kind: 'expert' as const, best_score: 0, attempts: 0, problem_id: 12, name: 'Task Order', slug: 'task-order', difficulty: 'Hard' },
  { position: 3, kind: 'real_world' as const, best_score: 0, attempts: 0, problem_id: 13, name: 'Fix the Report', slug: 'fix-report', difficulty: 'Hard' },
];
const assessment = {
  id: 5, status: 'in_progress' as const, technology: 'Python', started_at: null, deadline_at: '2026-10-12T15:00:00Z',
  finished_at: null, score: null, passed: null, items,
};
const problem = (position: number) => ({
  id: 10 + position, name: items[position - 1].name, slug: items[position - 1].slug, description: 'Do it.',
  difficulty: 'Hard', language: 'python', question_type: 'code', max_score: 100, progress: '', best_score: 0, attempts: 0, sequence: 1,
  kind: items[position - 1].kind, position, input_format: 'n', output_format: 'x', constraints: 'small', examples: [], starter_code: '# go\n',
});
const base: CodeForgeFlowState = { step: 'awaiting_problem', sessionToken: 's', courses: [], technologies: [], topics: [], problems: [] };

beforeEach(() => {
  jest.mocked(api.getAssessmentProblem).mockImplementation(async (_s, _id, position) => ({ problem: problem(position) }) as never);
});

test('an assessment opens its first problem, switches problems, keeps the best score and has no tutor', async () => {
  const started = await enterAssessment(base, assessment, { slug: 'python', name: 'Python' });
  expect(started.messages[0].text).toContain('Professional assessment · Python: 3 problems');
  expect(started.state.step).toBe('awaiting_code');
  expect(started.state.problemId).toBe(11);
  expect(started.messages[1].options?.map((o) => o.value)).toEqual(['assessment_problem_2', 'assessment_problem_3', 'finish_assessment']);

  const tutor = await handleCodeForgeText(started.state, 'explain_error');
  expect(tutor.messages[0].text).toContain('The AI tutor is off');
  expect(api.askTutor).not.toHaveBeenCalled();

  jest.mocked(api.submitProblem).mockResolvedValue({ submissionId: 1, mode: 'submit', status: 'Wrong Answer', score: 60, passedTests: 3, totalTests: 5, tests: [] });
  const submitted = await submitCodeForgeCode(started.state, 'print(1)');
  expect(submitted.state.assessment?.items[0].best_score).toBe(60);
  expect(submitted.messages[0].text).toContain('Best for this problem: 60/100');

  const second = await handleCodeForgeText(submitted.state, 'assessment_problem_2');
  expect(second.state.problemId).toBe(12);
  expect(second.messages[0].text).toContain('Problem 2 of 3 · Expert problem');
});

test('finishing shows the result and leaves the assessment', async () => {
  const started = await enterAssessment(base, assessment, { slug: 'python', name: 'Python' });
  jest.mocked(api.finishAssessment).mockResolvedValue({ assessment: { ...assessment, status: 'submitted', score: 73.3, passed: true,
    items: items.map((i, n) => ({ ...i, best_score: [100, 60, 60][n] })) } } as never);
  const done = await handleCodeForgeText(started.state, 'finish_assessment');
  expect(done.state.assessment).toBeUndefined();
  expect(done.messages[0].text).toContain('✅ Passed with 73.3/100.');
  expect(done.messages[0].text).toContain('Problem 3 (Real-world task): 60/100');
});
