const mockOverview = jest.fn();
const mockUsers = jest.fn();
const mockUserDetail = jest.fn();
const mockConversation = jest.fn();
const mockPayments = jest.fn();
const mockAgents = jest.fn();
jest.mock('../../src/lib/adminApi', () => ({
  fetchOverview: (...a: unknown[]) => mockOverview(...a),
  fetchUsers: (...a: unknown[]) => mockUsers(...a),
  fetchUserDetail: (...a: unknown[]) => mockUserDetail(...a),
  fetchConversation: (...a: unknown[]) => mockConversation(...a),
  fetchPayments: (...a: unknown[]) => mockPayments(...a),
  fetchAgents: (...a: unknown[]) => mockAgents(...a),
}));

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import DashboardPanel from '../../src/components/admin/DashboardPanel';
import UsersPanel from '../../src/components/admin/UsersPanel';
import PaymentsPanel from '../../src/components/admin/PaymentsPanel';
import AgentsPanel from '../../src/components/admin/AgentsPanel';

const day = (date: string, amount: number) => ({ date, amount, count: amount ? 1 : 0 });
const overview = {
  generated_at: '2026-09-26T10:00:00',
  users: { total: 42, new_7d: 5, new_30d: 12, admins: 1 },
  revenue: {
    currency: 'INR', total: 12345.5, last_30d: 4999, last_7d: 999, paid_count: 9, paying_customers: 6, by_status: { paid: 9, created: 3, failed: 1 },
    by_plan: [{ plan_id: 'basic', label: 'Basic plan', count: 5, amount: 2495 }],
    daily: [day('2026-09-25', 0), day('2026-09-26', 999)],
  },
  tokens: { outstanding_balance: 1500000, credited_by_payments: 3000000, users_out_of_tokens: 2 },
  activity: { conversations: 80, messages: 900, active_users_7d: 17, by_agent: [{ agent_id: 'capstone-project', chats: 15, users: 8, messages: 300, last_active: null }] },
  agents: { registered: 8, healthy: 7 },
  recent_signups: [{ id: 'u1', name: 'Asha Rao', email: 'asha@x.io', created_at: '2026-09-25T08:00:00' }],
  recent_payments: [{ id: 'p1', email: 'asha@x.io', label: 'Basic plan', amount: 499, status: 'paid', created_at: '2026-09-25T08:00:00' }],
};

beforeEach(() => { [mockOverview, mockUsers, mockUserDetail, mockConversation, mockPayments, mockAgents].forEach((m) => m.mockReset()); });

test('the dashboard shows money, users, tokens, agents online and usage per agent', async () => {
  mockOverview.mockResolvedValue(overview);
  render(<DashboardPanel />);
  expect(await screen.findByText('Total revenue')).toBeInTheDocument();
  expect(screen.getByText(/12,345\.50/)).toBeInTheDocument();
  expect(screen.getByText('9 paid payments')).toBeInTheDocument();
  expect(screen.getByText('7 / 8')).toBeInTheDocument();
  expect(screen.getByText('30,00,000')).toBeInTheDocument();          // Indian digit grouping
  expect(screen.getByText('2 users out of tokens')).toBeInTheDocument();
  expect(screen.getAllByText('Basic plan', { selector: 'td' })).toHaveLength(2);      // the by-plan table and the latest payments
  expect(screen.getByText(/Capstone Project Agent/)).toBeInTheDocument();
  expect(screen.getByRole('img', { name: /Daily revenue/ })).toBeInTheDocument();
});

test('a dashboard failure is shown with a retry, not a blank page', async () => {
  mockOverview.mockRejectedValueOnce(new Error('Administrator access is required.')).mockResolvedValue(overview);
  render(<DashboardPanel />);
  expect(await screen.findByText(/Administrator access is required/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByText('Total revenue')).toBeInTheDocument();
});

const userRow = { id: 'asha', name: 'Asha Rao', email: 'asha@x.io', mobile: '99999', is_admin: false, google: false, created_at: '2026-09-20T08:00:00', token_balance: 120000, paid_total: 599, chats: 2, agents_used: 2, last_active: '2026-09-26T08:00:00' };
const detail = {
  user: { id: 'asha', name: 'Asha Rao', email: 'asha@x.io', mobile: '99999', is_admin: false, google: false, created_at: '2026-09-20T08:00:00', token_balance: 120000, consent_accepted_at: null, consent_policy_version: null },
  totals: { paid: 599, payments: 2, paid_payments: 2, tokens_bought: 600000, conversations: 1, messages: 2 },
  payments: [{ id: 'p1', label: 'Basic plan', plan_id: 'basic', amount: 499, currency: 'INR', status: 'paid', razorpay_order_id: 'o1', razorpay_payment_id: 'pay_1', created_at: '2026-09-24T08:00:00', paid_at: '2026-09-24T08:01:00', tokens: 500000 }],
  conversations: [{ id: 'c1', agent_id: 'capstone-project', title: 'my python project', messages: 2, pinned: false, created_at: null, updated_at: '2026-09-26T08:00:00', deleted: false }],
  agent_progress: [{ agent_id: 'capstone', chat_id: 'c1', step: 'awaiting_submission', updated_at: '2026-09-26T08:00:00' }],
};

test('users: search, open a user, see their payments and progress, and read a conversation', async () => {
  mockUsers.mockResolvedValue({ total: 1, page: 1, limit: 25, users: [userRow] });
  mockUserDetail.mockResolvedValue(detail);
  mockConversation.mockResolvedValue({ id: 'c1', agent_id: 'capstone-project', title: 'my python project', messages: [
    { role: 'agent', content: 'What topic?', time: '09:59', created_at: null }, { role: 'user', content: 'python', time: '10:00', created_at: null }] });
  render(<UsersPanel />);

  fireEvent.change(await screen.findByLabelText('Search users'), { target: { value: 'asha' } });
  fireEvent.click(screen.getByRole('button', { name: 'Search' }));
  await waitFor(() => expect(mockUsers).toHaveBeenLastCalledWith(expect.objectContaining({ search: 'asha', page: 1 })));

  fireEvent.click(await screen.findByText('Asha Rao'));
  expect(await screen.findByText('Paid so far')).toBeInTheDocument();
  expect(mockUserDetail).toHaveBeenCalledWith('asha');
  expect(screen.getByText('awaiting submission')).toBeInTheDocument();
  expect(screen.getByText('pay_1')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Read' }));
  expect(await screen.findByText('What topic?')).toBeInTheDocument();
  expect(mockConversation).toHaveBeenCalledWith('asha', 'c1');
  expect(screen.getByText('python', { selector: 'p' })).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /All users/ }));
  expect(await screen.findByLabelText('Search users')).toBeInTheDocument();
});

test('users: paging asks the server for the next page', async () => {
  mockUsers.mockResolvedValue({ total: 60, page: 1, limit: 25, users: [userRow] });
  render(<UsersPanel />);
  await screen.findByText('Asha Rao');
  fireEvent.click(screen.getByRole('button', { name: 'Next →' }));
  await waitFor(() => expect(mockUsers).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
});

test('payments: shows every payment and filters by status on the server', async () => {
  const payment = { id: 'p1', user_id: 'asha', email: 'asha@x.io', name: 'Asha Rao', label: 'Basic plan', amount: 499, currency: 'INR', status: 'paid', razorpay_order_id: 'o1', razorpay_payment_id: 'pay_1', created_at: '2026-09-24T08:00:00', paid_at: '2026-09-24T08:01:00', tokens: 500000 };
  mockPayments.mockResolvedValue({ total: 1, page: 1, limit: 25, summary: { paid: { count: 1, amount: 499 } }, payments: [payment] });
  render(<PaymentsPanel />);
  const table = within(await screen.findByRole('table'));
  expect(table.getByText('asha@x.io')).toBeInTheDocument();
  expect(table.getByText('5,00,000')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Filter by status'), { target: { value: 'failed' } });
  await waitFor(() => expect(mockPayments).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'failed', page: 1 })));
});

test('agents: online and offline are clear, usage is joined to the chat agent, unconnected ones are listed', async () => {
  const base = { version: 'v1', endpoint: 'http://capstone:8000/api/invoke', owner: 'DigiDARA', plan_tier: 'free', status: 'healthy', last_heartbeat: null };
  mockAgents.mockResolvedValue({
    agents: [
      { ...base, agent_name: 'capstone_project_agent', description: 'Runs projects', heartbeat_age_seconds: 12, online: true, actions: ['health', 'status'] },
      { ...base, agent_name: 'old_agent', description: 'Old one', heartbeat_age_seconds: 20000, online: false, actions: [] },
    ],
    chat_usage: [{ agent_id: 'capstone-project', chats: 15, users: 8, messages: 300, last_active: null }],
  });
  render(<AgentsPanel />);
  expect(await screen.findByText('Capstone Project Agent')).toBeInTheDocument();
  expect(screen.getByText('online')).toBeInTheDocument();
  expect(screen.getByText('offline')).toBeInTheDocument();
  expect(screen.getByText('12s ago')).toBeInTheDocument();
  expect(screen.getByText('300')).toBeInTheDocument();
  expect(screen.getByText('Listed in the store but not connected')).toBeInTheDocument();
  expect(screen.getByText(/Research Agent/, { selector: 'span' })).toBeInTheDocument();
});
