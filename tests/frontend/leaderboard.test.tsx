jest.mock('../../src/lib/learnerApi', () => ({ fetchLeaderboard: jest.fn(), fetchReadiness: jest.fn().mockResolvedValue({}), setLeaderboardHidden: jest.fn() }));

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Leaderboard, { TopPerformers } from '../../src/components/Leaderboard';
import * as learnerApi from '../../src/lib/learnerApi';

const api = jest.mocked(learnerApi);
const entry = (rank: number, name: string, score: number, extra: object = {}) => ({
  rank, user_id: `u${rank}`, name, score, band: 'developing' as const, organization: null, is_me: false, ...extra,
});
const board = (extra: object = {}) => ({
  scope: 'organization' as const, group: 'students' as const, allowed_groups: ['students' as const],
  allowed_scopes: ['organization' as const, 'platform' as const],
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

test('a student switches between my organization and the whole platform', async () => {
  render(<Leaderboard />);
  await waitFor(() => expect(api.fetchLeaderboard).toHaveBeenCalledWith('auto', undefined));
  fireEvent.click(await screen.findByRole('tab', { name: 'Whole platform' }));
  await waitFor(() => expect(api.fetchLeaderboard).toHaveBeenLastCalledWith('platform', undefined));
});

test('staff see only their organization staff board, with what they are ranked on', async () => {
  const staff = { students: 12, average_readiness: 48.2, active_percent: 75 };
  api.fetchLeaderboard.mockResolvedValue(board({
    group: 'staff', allowed_groups: ['staff'], allowed_scopes: ['organization'],
    top: [entry(1, 'Priya K.', 56.3, { staff })], entries: [entry(1, 'Priya K.', 56.3, { staff })], me: { rank: 1, score: 56.3 },
  }));
  render(<Leaderboard />);
  expect(await screen.findByText('Top staff at Anna University')).toBeInTheDocument();
  expect(screen.queryByRole('tab', { name: 'Whole platform' })).not.toBeInTheDocument();
  expect(screen.getAllByText('12 students · avg readiness 48 · 75% active').length).toBeGreaterThan(0);
});

test('the chat home shows the top 3 of my organization, and opens the leaderboard', async () => {
  const onOpen = jest.fn();
  render(<TopPerformers onOpen={onOpen} />);
  const card = await screen.findByRole('complementary', { name: 'Top 3 at Anna University' });
  expect(within(card).getByText('Top performers')).toBeInTheDocument();
  expect(within(card).getByText('Asha R.')).toBeInTheDocument();
  expect(within(card).getByText('New in Top 3')).toBeInTheDocument();
  expect(within(card).getByText('#4', { selector: 'b' })).toBeInTheDocument();
  expect(api.fetchLeaderboard).toHaveBeenCalledWith('auto');
  fireEvent.click(within(card).getByRole('button', { name: 'View leaderboard →' }));
  expect(onOpen).toHaveBeenCalled();
});

test('a staff member sees their staff score apart from their own job readiness', async () => {
  api.fetchLeaderboard.mockResolvedValue(board({
    group: 'staff', allowed_groups: ['staff'], allowed_scopes: ['organization'], total: 2,
    top: [entry(1, 'Rubiking', 33, { is_me: true, staff: { students: 1, average_readiness: 4, active_percent: 100 } })],
    entries: [entry(1, 'Rubiking', 33, { is_me: true, staff: { students: 1, average_readiness: 4, active_percent: 100 } })],
    me: { rank: 1, score: 33, own_readiness: 84 },
  }));
  const { container } = render(<Leaderboard />);
  await waitFor(() => expect(container.querySelector('.lb-foot')).toHaveTextContent('33 staff score'));
  const footer = container.querySelector('.lb-foot') as HTMLElement;
  expect(footer).toHaveTextContent('your own job readiness is 84 (not part of the staff score)');
  expect(footer).not.toHaveTextContent('33 readiness');
});

test('admins can switch between the students and staff boards', async () => {
  api.fetchLeaderboard.mockResolvedValue(board({ allowed_groups: ['students', 'staff'] }));
  render(<Leaderboard />);
  fireEvent.click(await screen.findByRole('tab', { name: 'Staff' }));
  await waitFor(() => expect(api.fetchLeaderboard).toHaveBeenLastCalledWith('auto', 'staff'));
});

test('a learner can hide themselves', async () => {
  render(<Leaderboard />);
  fireEvent.click(await screen.findByRole('button', { name: 'Hide me' }));
  await waitFor(() => expect(api.setLeaderboardHidden).toHaveBeenCalledWith(true));
});

test('profile pictures show, and the initial when there is none', async () => {
  api.fetchLeaderboard.mockResolvedValue(board({
    top: [entry(1, 'Asha R.', 92, { avatar: 'data:image/jpeg;base64,AAAA' }), entry(2, 'Nila F.', 85), entry(3, 'Ravi T.', 80)],
  }));
  const { container } = render(<TopPerformers />);
  await screen.findByText('Asha R.');
  const pictures = container.querySelectorAll('.lb-avatar img');
  expect(pictures).toHaveLength(1);
  expect(pictures[0].getAttribute('src')).toBe('data:image/jpeg;base64,AAAA');
  expect(within(container).getByText('N')).toBeInTheDocument();
});
