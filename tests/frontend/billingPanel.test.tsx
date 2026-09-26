jest.mock('../../src/lib/billingApi', () => ({
  createBillingOrder: jest.fn(),
  createTopupOrder: jest.fn(),
  downloadInvoice: jest.fn(),
  fetchBillingPlans: jest.fn(),
  fetchBillingSummary: jest.fn(),
  fetchTokenBalance: jest.fn(),
  loadRazorpay: jest.fn(),
  verifyBillingPayment: jest.fn(),
}));

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import BillingPanel from '../../src/components/BillingPanel';
import * as api from '../../src/lib/billingApi';

const user = { id: 'u1', name: 'Asha Rao', email: 'asha@example.com', mobile: '9999999999', initial: 'A' };
const mocked = jest.mocked(api);

const plan = (id: string, name: string, amount: number, tokens: number, extra = {}) => ({
  id, name, amount, currency: 'INR', period: 'month', tokens, bonus_percent: 0, description: `${name} plan`, features: [`${tokens.toLocaleString()} tokens credited instantly`], popular: false, ...extra,
});
const catalog = {
  plans: [plan('basic', 'Basic', 49900, 500000), plan('standard', 'Standard', 99900, 1200000, { popular: true }), plan('premium', 'Premium', 199900, 2600000)],
  custom: { id: 'custom', name: 'Custom', description: 'Choose your own amount.', tokens_per_rupee: 1000, min_amount_inr: 1 },
};
const payments = [
  { id: 'paid-1', plan_id: 'standard', label: 'Standard plan', amount: 99900, currency: 'INR', status: 'paid', payment_id: 'pay_1', created_at: '2026-09-14T10:00:00Z', invoice_available: true },
  { id: 'paid-2', plan_id: 'topup_10000', label: 'Token top-up (10,000 tokens)', amount: 1000, currency: 'INR', status: 'paid', payment_id: 'pay_2', created_at: '2026-09-10T10:00:00Z', invoice_available: true },
  { id: 'open-1', plan_id: 'premium', label: 'Premium plan', amount: 199900, currency: 'INR', status: 'created', payment_id: null, created_at: '2026-09-07T10:00:00Z', invoice_available: false },
];

function setup(summary = { plan: 'free', plan_name: 'Free', plan_expires_at: null as string | null, payments }) {
  mocked.fetchBillingPlans.mockResolvedValue(catalog);
  mocked.fetchBillingSummary.mockResolvedValue({ ...summary });
  mocked.fetchTokenBalance.mockResolvedValue({ balance: 1250000 });
  const toast = jest.fn();
  render(<BillingPanel open user={user} onToast={toast} />);
  return toast;
}

afterEach(() => jest.clearAllMocks());

test('shows Basic, Standard, Premium and a Custom plan, each with its price', async () => {
  setup();
  const cards = await waitFor(() => {
    const found = ['basic', 'standard', 'premium', 'custom'].map((id) => document.querySelector(`[data-plan="${id}"]`) as HTMLElement | null);
    expect(found.every(Boolean)).toBe(true);
    return found as HTMLElement[];
  });
  expect(within(cards[0]).getByText('₹499')).toBeInTheDocument();
  expect(within(cards[1]).getByText('₹999')).toBeInTheDocument();
  expect(within(cards[2]).getByText('₹1,999')).toBeInTheDocument();
  expect(within(cards[1]).getByText('Most Popular')).toBeInTheDocument();
  expect(within(cards[3]).getByText('you choose')).toBeInTheDocument();
  expect(screen.queryByText(/Pro Monthly|Pro Annual/)).not.toBeInTheDocument();
});

test('buying a plan orders that plan id', async () => {
  mocked.createBillingOrder.mockRejectedValue(new Error('stop here'));
  const toast = setup();
  fireEvent.click(await screen.findByRole('button', { name: 'Buy Standard' }));
  await waitFor(() => expect(mocked.createBillingOrder).toHaveBeenCalledWith('standard'));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('stop here'));
});

test('the custom plan pays the amount typed, at 1,000 tokens per rupee, and the field can be cleared', async () => {
  mocked.createTopupOrder.mockRejectedValue(new Error('stop here'));
  setup();
  const input = await screen.findByLabelText('Amount (INR)');
  fireEvent.change(input, { target: { value: '' } });
  expect(input).toHaveValue(null); // not snapped back to a number while retyping
  fireEvent.change(input, { target: { value: '2500' } });
  expect(screen.getByText('2,500,000 tokens credited instantly')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Pay ₹2,500/ }));
  await waitFor(() => expect(mocked.createTopupOrder).toHaveBeenCalledWith(2500));
});

test('an empty or zero custom amount is raised to the minimum rather than ordering nothing', async () => {
  mocked.createTopupOrder.mockRejectedValue(new Error('stop here'));
  setup();
  fireEvent.change(await screen.findByLabelText('Amount (INR)'), { target: { value: '0' } });
  fireEvent.click(screen.getByRole('button', { name: /Pay ₹1$/ }));
  await waitFor(() => expect(mocked.createTopupOrder).toHaveBeenCalledWith(1));
});

test('history uses real labels and offers an invoice only for paid payments', async () => {
  setup();
  expect(await screen.findByText('Token top-up (10,000 tokens)')).toBeInTheDocument();
  expect(screen.getByText('Standard plan', { selector: 'b' })).toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: /Download invoice/ })).toHaveLength(2);
  expect(screen.queryByRole('button', { name: 'Download invoice for Premium plan' })).not.toBeInTheDocument();
});

test('clicking Invoice downloads that payment\'s invoice', async () => {
  mocked.downloadInvoice.mockResolvedValue('DD-202609-ABCDEF12.pdf');
  setup();
  fireEvent.click(await screen.findByRole('button', { name: 'Download invoice for Token top-up (10,000 tokens)' }));
  await waitFor(() => expect(mocked.downloadInvoice).toHaveBeenCalledWith('paid-2'));
});

test('a failed invoice download is reported, not swallowed', async () => {
  mocked.downloadInvoice.mockRejectedValue(new Error('Invoice not found.'));
  const toast = setup();
  fireEvent.click(await screen.findByRole('button', { name: 'Download invoice for Standard plan' }));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Invoice not found.'));
});

test('the current plan card reflects a paid plan, and a top-up alone is still Free', async () => {
  const soon = new Date(Date.now() + 10 * 864e5).toISOString();
  setup({ plan: 'premium', plan_name: 'Premium', plan_expires_at: soon, payments });
  expect(await screen.findByText('DigiDARA Premium')).toBeInTheDocument();
  expect(screen.getByText('Active')).toBeInTheDocument();
});

test('with no paid plan the account shows as Free', async () => {
  setup();
  expect(await screen.findByText('DigiDARA Free')).toBeInTheDocument();
});
