jest.mock('../../src/lib/codeforgeApi', () => ({ getProblemSet: jest.fn(), getAssessmentOverview: jest.fn(), startAssessment: jest.fn() }));

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CodeForgeProblemSet from '../../src/components/CodeForgeProblemSet';
import * as api from '../../src/lib/codeforgeApi';

const base = { description: '', max_score: 100, language: 'python', question_type: 'code' as const, sequence: 1, best_score: 0, attempts: 0 };
const problem = (number: number, name: string, difficulty: 'Easy' | 'Medium' | 'Hard', locked: boolean, progress = 'Not Started') => ({
  ...base, id: number, number, name, slug: name.toLowerCase().replace(/ /g, '-'), difficulty, locked, progress,
  topic_slug: 'basics', topic_name: 'Basics',
});

const overview = (patch = {}) => ({
  technology: { slug: 'python', name: 'Python' }, available: true, eligible: false, minutes: 75, pass_mark: 70, passed: 0,
  active: null, attempts: [], ...patch,
});

beforeEach(() => {
  jest.mocked(api.getAssessmentOverview).mockResolvedValue(overview() as never);
  jest.mocked(api.getProblemSet).mockResolvedValue({
    level: 'Easy', level_name: 'Beginner', technology_slug: 'python', course_slug: 'genai',
    languages: [
      { slug: 'python', name: 'Python', course_slug: 'genai', counts: { Easy: { total: 2, solved: 1 }, Medium: { total: 1, solved: 0 }, Hard: { total: 1, solved: 0 } } },
      { slug: 'java', name: 'Java', course_slug: 'backend', counts: { Easy: { total: 5, solved: 0 }, Medium: { total: 0, solved: 0 }, Hard: { total: 0, solved: 0 } } },
    ],
    problems: [problem(1, 'Hello World', 'Easy', false, 'Solved'), problem(2, 'Leap Year', 'Easy', false),
      problem(3, 'Word Count', 'Medium', true), problem(4, 'Matrix Path', 'Hard', true)],
  });
});

test('every language is a tab, and only the learner level opens', async () => {
  const onOpen = jest.fn();
  render(<CodeForgeProblemSet open sessionToken="s" onClose={jest.fn()} onOpenProblem={onOpen} onAssessment={jest.fn()} />);
  expect(await screen.findByText('1. Hello World')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Java/ })).toBeInTheDocument();
  expect(screen.getByText(/solve all 2 of them \(1 done\) to unlock Medium/)).toBeInTheDocument();
  const locked = screen.getByText('3. Word Count').closest('button')!;
  expect(locked).toBeDisabled();
  fireEvent.click(screen.getByText('2. Leap Year'));
  expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ courseSlug: 'genai', technologySlug: 'python', technologyName: 'Python' }));
  fireEvent.click(screen.getByRole('button', { name: /Java/ }));
  expect(await screen.findByText('1. Hello World')).toBeInTheDocument();
  expect(api.getProblemSet).toHaveBeenLastCalledWith('s', 'java', undefined);
});

test('the Professional assessment is locked below Professional, and starts in the chat at Professional', async () => {
  const { unmount } = render(<CodeForgeProblemSet open sessionToken="s" onClose={jest.fn()} onOpenProblem={jest.fn()} onAssessment={jest.fn()} />);
  expect(await screen.findByText(/Unlocks at the Professional level/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Start assessment' })).not.toBeInTheDocument();
  unmount();

  const assessment = { id: 5, status: 'in_progress', technology: 'Python', started_at: null, deadline_at: '2026-10-12T15:00:00Z',
    finished_at: null, score: null, passed: null, items: [] };
  jest.mocked(api.getAssessmentOverview).mockResolvedValue(overview({ eligible: true, passed: 1,
    attempts: [{ ...assessment, id: 4, status: 'submitted', score: 82, passed: true }] }) as never);
  jest.mocked(api.startAssessment).mockResolvedValue({ assessment } as never);
  const onAssessment = jest.fn();
  render(<CodeForgeProblemSet open sessionToken="s" courseSlug="genai" onClose={jest.fn()} onOpenProblem={jest.fn()} onAssessment={onAssessment} />);
  expect(await screen.findByText('1 of 3 passed')).toBeInTheDocument();
  expect(screen.getByText(/82\/100 · Passed/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Start assessment' }));
  await waitFor(() => expect(onAssessment).toHaveBeenCalledWith(assessment, { slug: 'python', name: 'Python', courseSlug: 'genai' }));
  expect(api.startAssessment).toHaveBeenCalledWith('s', 'python');
});
