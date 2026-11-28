const mockPool = jest.fn();
const mockPoolUsers = jest.fn();
const mockSave = jest.fn();
const mockLive = jest.fn();
jest.mock('../../src/lib/adminApi', () => ({
  fetchOpenAIPool: (...a: unknown[]) => mockPool(...a),
  fetchOpenAIPoolUsers: (...a: unknown[]) => mockPoolUsers(...a),
  saveOpenAIBalance: (...a: unknown[]) => mockSave(...a),
  fetchOpenAILive: (...a: unknown[]) => mockLive(...a),
}));

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import OpenAITokensPanel from '../../src/components/admin/OpenAITokensPanel';

const base = {
  generated_at: '2026-11-27T10:00:00', spend_source: 'estimate', spent_usd: 0.5, allocated_tokens: 4000000, users_holding_tokens: 2, users_total: 3,
  new_user_tokens: 50000, usd_per_million_tokens: 0.2625, support_email: 'support@digidaratechnologies.com', exact_costs: false,
  last_alert_at: null, new_users_while_short: 0, entries: [],
};
const notSet = { ...base, status: 'not_set', balance_entry: null, spend_source: null, spent_usd: 0, remaining_usd: null, available_tokens: null, spare_tokens: null, shortfall_tokens: null, new_users_room: null };
const short = {
  ...base, status: 'short', balance_entry: { id: 'e1', balance_usd: 1, note: '', created_at: '2026-11-27T09:00:00' },
  remaining_usd: 0.5, available_tokens: 1904761, spare_tokens: 0, shortfall_tokens: 2095239, new_users_room: 0,
  last_alert_at: '2026-11-27T10:00:00', new_users_while_short: 3, entries: [{ id: 'e1', balance_usd: 1, note: 'first', created_at: '2026-11-27T09:00:00' }],
};
const users = {
  total: 2, page: 1, limit: 25, users: [
    { id: 'new', name: 'New Learner', email: 'new@x.io', created_at: '2026-11-26T09:00:00', token_balance: 2000000, used_tokens: 0, covered: false },
    { id: 'old', name: 'Old Learner', email: 'old@x.io', created_at: '2026-10-26T09:00:00', token_balance: 2000000, used_tokens: 12345, covered: true },
  ],
};

beforeEach(() => {
  [mockPool, mockPoolUsers, mockSave, mockLive].forEach((m) => m.mockReset());
  mockPoolUsers.mockResolvedValue(users);
  mockLive.mockResolvedValue({ connected: false, error: 'no_key' });
});

test('short: says by how much, that support was emailed, and which users are not covered', async () => {
  mockPool.mockResolvedValue(short);
  render(<OpenAITokensPanel />);
  expect(await screen.findByText('Not enough OpenAI credit.')).toBeInTheDocument();
  expect(screen.getByText(/short by 20,95,239 tokens/)).toBeInTheDocument();
  expect(screen.getByText(/support@digidaratechnologies.com was emailed/)).toBeInTheDocument();
  expect(screen.getByText(/3 new users joined while short/)).toBeInTheDocument();
  expect(await screen.findByText('not covered')).toBeInTheDocument();
  expect(screen.getByText('covered')).toBeInTheDocument();
  expect(screen.getByText('12,345')).toBeInTheDocument();
});

test('an admin enters the balance and the panel shows the new figures', async () => {
  mockPool.mockResolvedValue(notSet);
  mockSave.mockResolvedValue({ ...short, generated_at: '2026-11-27T10:05:00' });
  render(<OpenAITokensPanel />);
  expect(await screen.findByText(/No OpenAI balance entered yet/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('OpenAI credit balance in US dollars'), { target: { value: 'abc' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save balance' }));
  expect(await screen.findByText(/Enter the balance in US dollars/)).toBeInTheDocument();
  expect(mockSave).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText('OpenAI credit balance in US dollars'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Note'), { target: { value: 'first' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save balance' }));
  await waitFor(() => expect(mockSave).toHaveBeenCalledWith(1, 'first'));
  expect(await screen.findByText('Not enough OpenAI credit.')).toBeInTheDocument();
});

test('live from OpenAI: spending and tokens pulled from the platform, and Pull now asks again', async () => {
  mockPool.mockResolvedValue(short);
  mockLive.mockResolvedValue({
    connected: true, error: null, fetched_at: '2026-11-28T09:00:00', days: 30,
    today_usd: 1.25, month_usd: 42.5, period_usd: 80, period_tokens: 1500000, period_requests: 321,
    daily: [{ date: '2026-11-28', usd: 1.25, input_tokens: 1000, output_tokens: 200, requests: 3 }],
    by_model: [{ model: 'gpt-4o-mini', input_tokens: 1000, output_tokens: 200, requests: 3 }],
    by_line_item: [{ line_item: 'gpt-4o-mini, input', usd: 0.75 }],
  });
  render(<OpenAITokensPanel />);
  expect(await screen.findByText('Live from OpenAI')).toBeInTheDocument();
  expect(await screen.findByText('$42.50')).toBeInTheDocument();
  expect(screen.getByText('gpt-4o-mini')).toBeInTheDocument();
  expect(screen.getByText('gpt-4o-mini, input')).toBeInTheDocument();
  expect(mockLive).toHaveBeenLastCalledWith(false);
  fireEvent.click(screen.getByRole('button', { name: 'Pull now' }));
  await waitFor(() => expect(mockLive).toHaveBeenLastCalledWith(true));
});

test('live from OpenAI: says how to connect when there is no admin key', async () => {
  mockPool.mockResolvedValue(short);
  render(<OpenAITokensPanel />);
  expect(await screen.findByText(/Not connected to OpenAI yet/)).toBeInTheDocument();
});
