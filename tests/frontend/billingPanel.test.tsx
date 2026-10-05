jest.mock('../../src/lib/billingApi', () => ({
  createBillingOrder: jest.fn(),
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

const plan = (id: string, name: string, amount: number, tokens: number, points: number, extra = {}) => ({
  id, name, amount, currency: 'INR', period: 'month', tokens, points, bonus_percent: 0, description: `${name} plan`, features: [`${points} points credited instantly`], popular: false, ...extra,
});
const PAGE = 'https://rzp.io/rzp/6ypplegm';
const catalog = {
  plans: [plan('basic', 'Basic', 39900, 300000, 100), plan('standard', 'Standard', 79900, 700000, 250, { popular: true }), plan('premium', 'Premium', 99900, 900000, 500, { payment_page_url: PAGE })],
};
const payments = [
  { id: 'paid-1', plan_id: 'standard', label: 'Standard plan', amount: 99900, currency: 'INR', status: 'paid', payment_id: 'pay_1', created_at: '2026-09-14T10:00:00Z', invoice_available: true },
  { id: 'paid-2', plan_id: 'topup_10000', label: 'Points top-up', amount: 1000, currency: 'INR', status: 'paid', payment_id: 'pay_2', created_at: '2026-09-10T10:00:00Z', invoice_available: true },
  { id: 'open-1', plan_id: 'premium', label: 'Premium plan', amount: 199900, currency: 'INR', status: 'created', payment_id: null, created_at: '2026-09-07T10:00:00Z', invoice_available: false },
];

function setup(summary = { plan: 'free', plan_name: 'Free', plan_expires_at: null as string | null, payments }) {
  mocked.fetchBillingPlans.mockResolvedValue(catalog);
  mocked.fetchBillingSummary.mockResolvedValue({ ...summary });
  mocked.fetchTokenBalance.mockResolvedValue({ balance: 1250000, points: 416.66, tokens_per_point: 3000 });
  const toast = jest.fn();
  render(<BillingPanel open user={user} onToast={toast} />);
  return toast;
}

afterEach(() => jest.clearAllMocks());

test('shows Basic 399, Standard 799 and Premium 999, and no Custom plan', async () => {
  setup();
  const cards = await waitFor(() => {
    const found = ['basic', 'standard', 'premium'].map((id) => document.querySelector(`[data-plan="${id}"]`) as HTMLElement | null);
    expect(found.every(Boolean)).toBe(true);
    return found as HTMLElement[];
  });
  expect(within(cards[0]).getByText('₹399')).toBeInTheDocument();
  expect(within(cards[1]).getByText('₹799')).toBeInTheDocument();
  expect(within(cards[2]).getByText('₹999')).toBeInTheDocument();
  expect(within(cards[1]).getByText('Most Popular')).toBeInTheDocument();
  expect(document.querySelector('[data-plan="custom"]')).toBeNull();
  expect(screen.queryByLabelText('Amount (INR)')).not.toBeInTheDocument();
  expect(screen.queryByText(/Pro Monthly|Pro Annual/)).not.toBeInTheDocument();
});

test('the 999 plan opens the Razorpay payment page and asks for the account email', async () => {
  const open = jest.spyOn(window, 'open').mockReturnValue(null);
  setup();
  const premium = (await screen.findByRole('button', { name: 'Buy Premium' })).closest('article') as HTMLElement;
  expect(within(premium).getByText('asha@example.com')).toBeInTheDocument();
  fireEvent.click(within(premium).getByRole('button', { name: 'Buy Premium' }));
  expect(open).toHaveBeenCalledWith(PAGE, '_blank', 'noopener,noreferrer');
  expect(mocked.createBillingOrder).not.toHaveBeenCalled();
  expect(screen.getByRole('status')).toHaveTextContent('500 points appear here once Razorpay confirms');
  mocked.fetchTokenBalance.mockResolvedValue({ balance: 2150000, points: 916.66, tokens_per_point: 2345.46 });
  fireEvent.click(screen.getByRole('button', { name: 'Refresh balance' }));
  expect(await screen.findByText('916')).toBeInTheDocument();
  open.mockRestore();
});

test('buying a plan orders that plan id', async () => {
  mocked.createBillingOrder.mockRejectedValue(new Error('stop here'));
  const toast = setup();
  fireEvent.click(await screen.findByRole('button', { name: 'Buy Standard' }));
  await waitFor(() => expect(mocked.createBillingOrder).toHaveBeenCalledWith('standard'));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('stop here'));
});

test('history uses real labels and offers an invoice only for paid payments', async () => {
  setup();
  expect(await screen.findByText('Points top-up')).toBeInTheDocument();
  expect(screen.getByText('Standard plan', { selector: 'b' })).toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: /Download invoice/ })).toHaveLength(2);
  expect(screen.queryByRole('button', { name: 'Download invoice for Premium plan' })).not.toBeInTheDocument();
});

test('clicking Invoice downloads that payment\'s invoice', async () => {
  mocked.downloadInvoice.mockResolvedValue('DD-202609-ABCDEF12.pdf');
  setup();
  fireEvent.click(await screen.findByRole('button', { name: 'Download invoice for Points top-up' }));
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
