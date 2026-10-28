jest.mock('../../src/lib/learnerApi', () => ({ fetchLearningDashboard: jest.fn() }));

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import LearningDashboard from '../../src/components/LearningDashboard';
import * as learnerApi from '../../src/lib/learnerApi';

const api = jest.mocked(learnerApi);
const months = ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'];
const base = {
  view: 'me', views: ['me'], label: 'Your learning', people: 1,
  kpis: { readiness: 42, assessments: 5, submitted: 4, submission_rate: 80, average_score: 25, active_recently: 1, active_days: 7, requests_30d: 12 },
  monthly: months.map((month, i) => ({ month, requests: i, assigned: i === 5 ? 5 : 0, attempted: i === 5 ? 4 : 0 })),
  status: { submitted: 4, open: 0, in_progress: 0, upcoming: 0, missed: 1 },
  agents: [{ agent: 'aptitude_agent', requests: 12 }],
  areas: [{ label: 'Coding', average: 100 }],
  assessments: [{ title: 'Python basics', status: 'submitted' as const, score: 80, closes_at: null, opens_at: null }],
  learners: [],
};

beforeEach(() => api.fetchLearningDashboard.mockReset().mockResolvedValue(base as never));

test('a learner sees their own cards, the assessment status and their assessments', async () => {
  render(<LearningDashboard />);
  expect(await screen.findByText('Learning Dashboard')).toBeInTheDocument();
  expect((await screen.findByText('Job readiness')).parentElement).toHaveTextContent('42');
  expect(screen.getByText('Submission rate').parentElement).toHaveTextContent('80%');
  expect(screen.getByText('Average score').parentElement).toHaveTextContent('25%');
  const donut = screen.getByRole('img', { name: /Submitted 4, Open now 0, In progress 0, Upcoming 0, Missed 1/ });
  expect(donut).toBeInTheDocument();
  expect(screen.getByText('Python basics')).toBeInTheDocument();
  expect(screen.getByText('Aptitude Trainer')).toBeInTheDocument();
  expect(screen.queryByRole('tablist')).not.toBeInTheDocument();      // one view only
});

test('staff switch between their students and their own learning', async () => {
  api.fetchLearningDashboard.mockResolvedValue({
    ...base, view: 'students', views: ['students', 'me'], label: 'Your students at Anna University', people: 2,
    learners: [{ user_id: 'u1', name: 'Asha', readiness: 60, submitted: 1, assigned: 2, last_active_at: null }],
  } as never);
  render(<LearningDashboard />);
  expect(await screen.findByText(/Your students at Anna University · 2 learners/)).toBeInTheDocument();
  const table = screen.getByRole('table');
  expect(within(table).getByText('Asha')).toBeInTheDocument();
  expect(within(table).getByText('1 / 2')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('tab', { name: 'My learning' }));
  await waitFor(() => expect(api.fetchLearningDashboard).toHaveBeenLastCalledWith('me'));
});
