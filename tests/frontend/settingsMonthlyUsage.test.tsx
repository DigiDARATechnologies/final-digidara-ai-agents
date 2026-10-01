import { render, screen } from '@testing-library/react';
import SettingsModal from '../../src/components/SettingsModal';
import * as billing from '../../src/lib/billingApi';

jest.mock('../../src/lib/usageApi', () => ({
  fetchAllUsageSummaries: jest.fn().mockResolvedValue([
    { id: 'certificate_agent', label: 'AI Certification Agent', icon: '', color: '', online: true, tracked: true, usage: { total_tokens: 574100, total_requests: 2937 } },
    { id: 'mock_interview_agent', label: 'Mock Interview Agent', icon: '', color: '', online: true, tracked: true, usage: { total_tokens: 389400, total_requests: 602 } },
  ]),
}));
jest.mock('../../src/lib/billingApi', () => ({ fetchMonthlyUsage: jest.fn() }));
jest.mock('../../src/components/BillingPanel', () => ({ __esModule: true, default: () => null }));
jest.mock('../../src/components/SettingsExtras', () => ({ AppearanceSettings: () => null, SecuritySettings: () => null }));
jest.mock('../../src/lib/communicationApi', () => ({ bridgeIdentity: jest.fn(), getDashboard: jest.fn(), getHistory: jest.fn() }));

const user = { id: 'u', name: 'A', email: 'a@x.y', mobile: '1', initial: 'A' };
const openUsage = () => render(
  <SettingsModal open initialTab="usage" user={user} chats={[]} glowOn onClose={jest.fn()} onOpenChat={jest.fn()} onGlowToggle={jest.fn()}
    onClearHistory={jest.fn()} onToast={jest.fn()} onExportData={jest.fn()} onDeleteAccount={jest.fn()} />,
);

test('shows this month only, against the dynamic limit (used + balance), not a fixed 1M', async () => {
  jest.mocked(billing.fetchMonthlyUsage).mockResolvedValue({
    month_start: '2026-10-01T00:00:00Z', tokens_used: 30000, requests: 12, balance: 90000, limit: 120000,
    agents: [{ agent_name: 'certificate_agent', tokens: 30000, requests: 12 }],
  });
  openUsage();
  expect(await screen.findByText('30.0K of 120.0K tokens used this month')).toBeInTheDocument();
  expect(screen.getByText('75% remaining')).toBeInTheDocument();
  expect(screen.getByText('30.0K tokens')).toBeInTheDocument();
  // Per agent: this month's numbers, not the agents' all-time totals.
  expect(await screen.findByText('30.0K tokens · 12 requests')).toBeInTheDocument();
  expect(screen.getByText('0 tokens · 0 requests')).toBeInTheDocument();
  expect(screen.queryByText(/2937/)).not.toBeInTheDocument();
  expect(screen.queryByText(/1\.0M/)).not.toBeInTheDocument();
});

test('a new user starts the month at zero with their whole balance remaining', async () => {
  jest.mocked(billing.fetchMonthlyUsage).mockResolvedValue({
    month_start: '2026-10-01T00:00:00Z', tokens_used: 0, requests: 0, balance: 50000, limit: 50000, agents: [],
  });
  openUsage();
  expect(await screen.findByText('0 of 50.0K tokens used this month')).toBeInTheDocument();
  expect(screen.getByText('100% remaining')).toBeInTheDocument();
});
