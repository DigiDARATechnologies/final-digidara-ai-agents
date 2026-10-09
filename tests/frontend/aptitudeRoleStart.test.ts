/** Aptitude starts from the learner's role, skills and level. */
jest.mock('../../src/lib/aptitudeApi', () => ({
  abandonAptitudeTest: jest.fn(), createAptitudeTest: jest.fn(), ensureAptitudeSession: jest.fn(), getAptitudeQuestion: jest.fn(),
  getAptitudeResults: jest.fn(), requestAptitudeHint: jest.fn(), submitAptitudeAnswer: jest.fn(), downloadAptitudeReport: jest.fn(),
  skipAptitudeQuestion: jest.fn(), getMixedTestConfig: jest.fn(), saveMixedTestConfig: jest.fn(),
}));

import * as api from '../../src/lib/aptitudeApi';
import { handleAptitudeText, initialAptitudeMessage, roleFamily, type AptitudeFlowState } from '../../src/lib/aptitudeFlow';
import { setLearnerContext } from '../../src/lib/learnerContext';
import type { LearnerSummary } from '../../src/lib/learnerApi';

const user = { id: 'u1', name: 'Prem Kumar', email: 'prem@example.com', mobile: '', initial: 'P' };
const question = { test_id: 't1', sequence: 1, total_questions: 20, category: 'Technical Aptitude', topic: 'Loops', difficulty: 'Medium',
  question: 'Q?', options: { A: 'a', B: 'b' }, allowed_time_seconds: 60, hints_remaining: 3 };

function learner(role: string, level = 'medium'): LearnerSummary {
  return {
    profile: { target_role: role, degree: 'M.Sc', skills: ['java', 'python', 'llm'], experience: 'experienced', onboarding_completed: true, onboarding_completed_at: null },
    levels: [{ agent_name: 'aptitude_agent', agent_label: 'Aptitude', level: level as never, source: 'self', updated_at: null }],
    level_choices: [], consent_required: false, membership: null,
  };
}

const atMode: AptitudeFlowState = { step: 'awaiting_mode', sessionToken: 's' };

beforeEach(() => {
  // Starting a test refreshes the Aptitude session first.
  jest.mocked(api.ensureAptitudeSession).mockResolvedValue({ sessionToken: 's' } as never);
  jest.mocked(api.createAptitudeTest).mockResolvedValue({ test_id: 't1' } as never);
  jest.mocked(api.getAptitudeQuestion).mockResolvedValue(question as never);
});
afterEach(() => { setLearnerContext(null); jest.clearAllMocks(); });

test('roles are grouped by what their aptitude rounds test', () => {
  expect(roleFamily('AI Engineer')).toBe('engineering');
  expect(roleFamily('Data Analyst')).toBe('data');
  expect(roleFamily('Digital Marketing Executive')).toBe('business');
});

test('the opening offers a mixed test for the role and its focus area at the learner level', () => {
  setLearnerContext(learner('ai engineer'));
  const options = initialAptitudeMessage(user).options ?? [];
  expect(options[0]).toMatchObject({ value: 'role_mix', label: 'Mixed test for AI Engineer' });
  expect(options[1]).toMatchObject({ value: 'role_category', label: 'Technical Aptitude at your level' });
  expect(options[1].description).toContain('Intermediate · Java');
  expect(options.map((o) => o.value)).toEqual(['role_mix', 'role_category', 'mixed', 'category_practice']);
});

test('the focus area starts at once, at the learner level, in their own language', async () => {
  setLearnerContext(learner('ai engineer', 'hard'));
  const result = await handleAptitudeText(atMode, 'role_category', user);
  expect(api.createAptitudeTest).toHaveBeenCalledWith('s', { mode: 'category_practice', technical_language: 'Java', category: 'Technical Aptitude', level: 'Advanced' });
  expect(result.state.step).toBe('awaiting_question');
});

test('the role mix becomes the mixed test setup, then the test starts', async () => {
  setLearnerContext(learner('data analyst'));
  const categories = ['Quantitative Aptitude', 'Logical Reasoning', 'Verbal Ability', 'Analytical Reasoning', 'Computer Fundamentals', 'Technical Aptitude']
    .map((name, i) => ({ category_id: `c${i}`, category_name: name, question_count: 3, default_count: 3 }));
  jest.mocked(api.getMixedTestConfig).mockResolvedValue({ categories, total_questions: 18, limits: { min_per_category: 0, max_per_category: 10, max_total: 60 } });
  await handleAptitudeText(atMode, 'role_mix', user);
  expect(api.saveMixedTestConfig).toHaveBeenCalledWith('s', [
    { category_id: 'c0', question_count: 6 }, { category_id: 'c1', question_count: 4 }, { category_id: 'c2', question_count: 1 },
    { category_id: 'c3', question_count: 5 }, { category_id: 'c4', question_count: 1 }, { category_id: 'c5', question_count: 3 },
  ]);
  expect(api.createAptitudeTest).toHaveBeenCalledWith('s', { mode: 'mixed', technical_language: 'Java' });
});

test('without a profile the opening is unchanged', () => {
  expect(initialAptitudeMessage(user).options?.map((o) => o.value)).toEqual(['mixed', 'category_practice']);
});
