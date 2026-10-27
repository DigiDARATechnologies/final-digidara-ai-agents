jest.mock('../../src/lib/learnerApi', () => ({ fetchLeaderboard: jest.fn(), setLeaderboardHidden: jest.fn() }));

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Leaderboard from '../../src/components/Leaderboard';
import * as learnerApi from '../../src/lib/learnerApi';

const api = jest.mocked(learnerApi);
const entry = (rank: number, name: string, score: number, extra: object = {}) => ({
  rank, user_id: `u${rank}`, name, score, band: 'developing' as const, organization: null, is_me: false, ...extra,
});
const board = (extra: object = {}) => ({
  scope: 'platform' as const, group: 'students' as const, allowed_groups: ['students' as const],
  organization: { id: 'o1', name: 'Anna University' },
  top: [entry(1, 'Asha R.', 92), entry(2, 'Nila F.', 85, { new_in_top: true }), entry(3, 'Ravi T.', 80)],
  entries: [entry(1, 'Asha R.', 92), entry(2, 'Nila F.', 85, { new_in_top: true }), entry(3, 'Ravi T.', 80),
    entry(4, 'Learner O.', 40, { is_me: true })],
  total: 4, me: { rank: 4, score: 40 }, hidden: false, ...extra,
});

beforeEach(() => {
  jest.useFakeTimers();
  api.fetchLeaderboard.mockReset().mockResolvedValue(board());
  api.setLeaderboardHidden.mockReset().mockResolvedValue({ hidden: true });
});
afterEach(() => jest.useRealTimers());

test('shows the top 3 podium, the newcomer in the spotlight first, and my rank', async () => {
  render(<Leaderboard />);
  const podium = await screen.findByRole('list', { name: 'Top 3' });
  expect(within(podium).getByText('Asha R.')).toBeInTheDocument();
  expect(within(podium).getByText('New')).toBeInTheDocument();
  // The spotlight starts with whoever just broke into the top 3, then rotates.
  expect(screen.getByText('New in Top 3')).toBeInTheDocument();
  expect(screen.getByText(/#2 · 85 readiness/)).toBeInTheDocument();
  act(() => { jest.advanceTimersByTime(4000); });
  expect(screen.getByText(/#1 · 92 readiness/)).toBeInTheDocument();
  expect(screen.getByText('Learner O. (you)')).toBeInTheDocument();
  expect(screen.getByText('#4', { selector: 'b' })).toBeInTheDocument();
});

test('switches between the whole platform and my organization', async () => {
  render(<Leaderboard />);
  fireEvent.click(await screen.findByRole('tab', { name: 'My organization' }));
  await waitFor(() => expect(api.fetchLeaderboard).toHaveBeenLastCalledWith('organization', undefined));
});

test('admins can switch between the students and staff boards', async () => {
  api.fetchLeaderboard.mockResolvedValue(board({ allowed_groups: ['students', 'staff'] }));
  render(<Leaderboard />);
  fireEvent.click(await screen.findByRole('tab', { name: 'Staff' }));
  await waitFor(() => expect(api.fetchLeaderboard).toHaveBeenLastCalledWith('platform', 'staff'));
});

test('a learner can hide themselves', async () => {
  render(<Leaderboard />);
  fireEvent.click(await screen.findByRole('button', { name: 'Hide me' }));
  await waitFor(() => expect(api.setLeaderboardHidden).toHaveBeenCalledWith(true));
});
