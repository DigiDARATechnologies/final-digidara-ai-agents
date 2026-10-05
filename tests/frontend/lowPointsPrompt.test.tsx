jest.mock('../../src/lib/billingApi', () => ({
  fetchBillingPlans: jest.fn(),
  fetchTokenBalance: jest.fn(),
}));

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import LowPointsModal from '../../src/components/LowPointsModal';
import { useLowPointsPrompt } from '../../src/hooks/useLowPointsPrompt';
import * as api from '../../src/lib/billingApi';
import { reportPointsActivity } from '../../src/lib/points';

const mocked = jest.mocked(api);
const plan = (id: string, name: string, amount: number, points: number, popular = false) => ({
  id, name, amount, currency: 'INR', period: 'month', tokens: points * 2000, points, bonus_percent: 0, description: '', features: [], popular,
});

function Harness({ onBuy = jest.fn() }: { onBuy?: () => void }) {
  const prompt = useLowPointsPrompt(true);
  return prompt.open
    ? <LowPointsModal points={prompt.points} outOfPoints={prompt.outOfPoints} onClose={prompt.dismiss} onBuy={onBuy} />
    : <span>no popup</span>;
}

const balance = (points: number) => mocked.fetchTokenBalance.mockResolvedValue({ balance: points * 2000, points, tokens_per_point: 2000 });

beforeEach(() => {
  sessionStorage.clear();
  jest.clearAllMocks();
  mocked.fetchBillingPlans.mockResolvedValue({
    plans: [plan('basic', 'Basic', 39900, 250), plan('standard', 'Standard', 79900, 500, true), plan('premium', 'Premium', 99900, 750)],
  });
});

test('a low balance pops up the plans with their points and prices', async () => {
  balance(12.5);
  render(<Harness />);
  expect(await screen.findByRole('dialog', { name: "You're running low on points" })).toBeInTheDocument();
  expect(screen.getByText('12.5')).toBeInTheDocument();
  expect(await screen.findByText('250 points')).toBeInTheDocument();
  expect(screen.getByText('500 points')).toBeInTheDocument();
  expect(screen.getByText('750 points')).toBeInTheDocument();
  expect(screen.getByText('Most popular')).toBeInTheDocument();
});

test('enough points shows nothing', async () => {
  balance(300);
  render(<Harness />);
  await waitFor(() => expect(mocked.fetchTokenBalance).toHaveBeenCalled());
  expect(screen.getByText('no popup')).toBeInTheDocument();
});

test('Buy points goes to checkout', async () => {
  balance(3);
  const onBuy = jest.fn();
  render(<Harness onBuy={onBuy} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Buy points' }));
  expect(onBuy).toHaveBeenCalled();
});

test('the gateway saying "not enough points" pops it up as out of points, even after Later on a low balance', async () => {
  balance(10);
  render(<Harness />);
  fireEvent.click(await screen.findByRole('button', { name: 'Later' }));
  expect(screen.getByText('no popup')).toBeInTheDocument();

  balance(0);
  act(() => reportPointsActivity(402));
  expect(await screen.findByRole('dialog', { name: "You're out of points" })).toBeInTheDocument();
});

test('Later on a low balance is remembered for the session', async () => {
  balance(10);
  render(<Harness />);
  fireEvent.click(await screen.findByRole('button', { name: 'Later' }));
  act(() => { window.dispatchEvent(new Event('digidara:billing-updated')); });
  await waitFor(() => expect(mocked.fetchTokenBalance).toHaveBeenCalledTimes(2));
  expect(screen.getByText('no popup')).toBeInTheDocument();
});

test('a purchase that lifts the balance closes it and clears the dismissal', async () => {
  balance(10);
  render(<Harness />);
  await screen.findByRole('dialog');
  balance(260);
  act(() => { window.dispatchEvent(new Event('digidara:billing-updated')); });
  expect(await screen.findByText('no popup')).toBeInTheDocument();
  expect(sessionStorage.getItem('digidara_low_points_dismissed')).toBeNull();
});
