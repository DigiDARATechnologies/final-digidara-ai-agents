jest.mock('../../src/lib/codeforgeApi', () => ({ getProblemSet: jest.fn() }));

import { fireEvent, render, screen } from '@testing-library/react';
import CodeForgeProblemSet from '../../src/components/CodeForgeProblemSet';
import * as api from '../../src/lib/codeforgeApi';

const base = { description: '', max_score: 100, language: 'python', question_type: 'code' as const, sequence: 1, best_score: 0, attempts: 0 };
const problem = (number: number, name: string, difficulty: 'Easy' | 'Medium' | 'Hard', locked: boolean, progress = 'Not Started') => ({
  ...base, id: number, number, name, slug: name.toLowerCase().replace(/ /g, '-'), difficulty, locked, progress,
  topic_slug: 'basics', topic_name: 'Basics',
});

beforeEach(() => {
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
  render(<CodeForgeProblemSet open sessionToken="s" onClose={jest.fn()} onOpenProblem={onOpen} />);
  expect(await screen.findByText('1. Hello World')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Java/ })).toBeInTheDocument();
  expect(screen.getByText(/solve all 2 of them \(1 done\) to unlock Medium/)).toBeInTheDocument();
  const locked = screen.getByText('3. Word Count').closest('button')!;
  expect(locked).toBeDisabled();
  fireEvent.click(screen.getByText('2. Leap Year'));
  expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ courseSlug: 'genai', technologySlug: 'python', technologyName: 'Python' }));
  fireEvent.click(screen.getByRole('button', { name: /Java/ }));
  expect(api.getProblemSet).toHaveBeenLastCalledWith('s', 'java');
});
