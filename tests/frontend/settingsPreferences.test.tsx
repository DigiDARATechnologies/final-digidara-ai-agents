jest.mock('../../src/lib/accountApi', () => ({
  updateProfile: jest.fn(), fetchSignIns: jest.fn(), revokeSignIn: jest.fn(), signOutOtherDevices: jest.fn(),
  fetchTwoStep: jest.fn(), startTwoStep: jest.fn(), enableTwoStep: jest.fn(), disableTwoStep: jest.fn(), fetchUsageRange: jest.fn(),
}));
jest.mock('../../src/lib/authApi', () => ({ googleAuthUrl: jest.fn(), resendTwoStepCode: jest.fn() }));

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { formatDate, setDatePrefs } from '../../src/lib/dateFormat';
import { pinnedFirst } from '../../src/lib/pinnedAgents';
import { messageToSpeech } from '../../src/lib/voiceCaption';
import { handleShortcut } from '../../src/lib/shortcuts';
import { applyAppearance, loadAppearance } from '../../src/lib/appearance';
import { agentChatsMarkdown, NotificationSettings, usageCsv } from '../../src/components/SettingsSections';
import LoginOverlay from '../../src/components/LoginOverlay';
import type { AccountPrefs } from '../../src/lib/accountApi';

const PREFS: AccountPrefs = {
  notifications: { email: true, in_app: true, assessment_reminders: true, low_coin_warning: true, weekly_progress: false },
  general: { default_agent: '', time_zone: '', date_format: 'auto' },
  usage: { warn_percent: 80 },
  billing: { billing_email: '', renewal_reminder: true },
  pinned_agents: [],
};

afterEach(() => {
  setDatePrefs('', 'auto');
  localStorage.clear();
});

test('dates follow the chosen format and time zone', () => {
  // 20:30 UTC on 1 Nov is already 2 Nov in India.
  const moment = Date.UTC(2026, 10, 1, 20, 30);
  setDatePrefs('Asia/Kolkata', 'dmy');
  expect(formatDate(moment)).toBe('02/11/2026');
  setDatePrefs('UTC', 'mdy');
  expect(formatDate(moment)).toBe('11/01/2026');
  setDatePrefs('UTC', 'ymd');
  expect(formatDate(moment)).toBe('2026-11-01');
  setDatePrefs('Not/AZone', 'ymd');
  expect(formatDate(moment)).toMatch(/^2026-11-0[12]$/);
});

test('pinned agents come first, in the order they were pinned', () => {
  const agents = [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }];
  expect(pinnedFirst(agents, ['c', 'a']).map((agent) => agent.id)).toEqual(['c', 'a', 'b', 'd']);
  expect(pinnedFirst(agents, [])).toBe(agents);
});

test('a voice caption is plain text and follows the end of a long reply', () => {
  expect(messageToSpeech('**Hello** [there](https://x.y)! `code`')).toBe('Hello there! code');
  const caption = messageToSpeech('word '.repeat(100), 40);
  expect(caption.startsWith('…')).toBe(true);
  expect(caption.length).toBeLessThanOrEqual(41);
});

test('shortcuts run their action, and stop when switched off', () => {
  const actions = { newChat: jest.fn(), openSettings: jest.fn(), toggleSidebar: jest.fn(), showShortcuts: jest.fn() };
  const key = (init: KeyboardEventInit) => new KeyboardEvent('keydown', init);
  applyAppearance({ ...loadAppearance(), shortcuts: true });
  expect(handleShortcut(key({ key: 'O', ctrlKey: true, shiftKey: true }), actions)).toBe(true);
  expect(handleShortcut(key({ key: ',', metaKey: true }), actions)).toBe(true);
  expect(actions.newChat).toHaveBeenCalledTimes(1);
  expect(actions.openSettings).toHaveBeenCalledTimes(1);
  expect(handleShortcut(key({ key: 'x', ctrlKey: true }), actions)).toBe(false);
  applyAppearance({ ...loadAppearance(), shortcuts: false });
  expect(handleShortcut(key({ key: 'b', ctrlKey: true }), actions)).toBe(false);
  expect(actions.toggleSidebar).not.toHaveBeenCalled();
});

test('appearance saved before the new options still loads, with defaults for the rest', () => {
  localStorage.setItem('digidara_appearance', JSON.stringify({ accent: 'green', reduceMotion: true }));
  expect(loadAppearance()).toMatchObject({ accent: 'green', reduceMotion: true, theme: 'light', textSize: 'normal', bubbles: 'rounded', shortcuts: true, captions: false });
  localStorage.setItem('digidara_appearance', JSON.stringify({ theme: 'neon', textSize: 'huge', compact: 'yes' }));
  expect(loadAppearance()).toMatchObject({ theme: 'light', textSize: 'normal', compact: false });
  applyAppearance({ ...loadAppearance(), theme: 'dark', textSize: 'large', highContrast: true });
  expect(document.documentElement.dataset).toMatchObject({ theme: 'dark', text: 'large', contrast: 'high' });
});

test('usage export is a CSV with one row per charge', () => {
  setDatePrefs('UTC', 'ymd');
  const csv = usageCsv({
    start: '2026-11-01', end: '2026-11-02', tokens_used: 0, points_used: 3, requests: 2, agents: [], days: [],
    events: [
      { at: '2026-11-02T10:00:00Z', agent_name: 'codeforge', action: 'run, "fast"', tokens: 3000, points: 1 },
      { at: '2026-11-01T10:00:00Z', agent_name: 'aptitude', action: 'test', tokens: 6000, points: 2 },
    ],
  });
  const lines = csv.split('\n');
  expect(lines[0]).toBe('Date,Time,Agent,Action,Coins');
  expect(lines).toHaveLength(3);
  expect(lines[1]).toContain('2026-11-02');
  expect(lines[1]).toContain('"run, ""fast"""');
});

test('an agent chat export has every chat and message', () => {
  const markdown = agentChatsMarkdown('CodeForge', [
    { id: '1', agentId: 'codeforge', title: 'Arrays', updatedAt: 0, messages: [{ role: 'user', text: 'Hi', time: '10:00' }, { role: 'agent', text: 'Hello!', time: '10:01' }] },
    { id: '2', agentId: 'codeforge', title: 'Strings', updatedAt: 0, messages: [] },
  ]);
  expect(markdown).toContain('# CodeForge — chats');
  expect(markdown).toContain('## Arrays');
  expect(markdown).toContain('## Strings');
  expect(markdown).toContain('**You** (10:00):');
  expect(markdown).toContain('Hello!');
});

test('email switches are disabled while emails are off', async () => {
  const onPrefs = jest.fn().mockResolvedValue(undefined);
  render(<NotificationSettings prefs={{ ...PREFS, notifications: { ...PREFS.notifications, email: false } }} onPrefs={onPrefs} onToast={jest.fn()} />);
  expect(screen.getByLabelText('Weekly progress email')).toBeDisabled();
  expect(screen.getByLabelText('In-app alerts')).not.toBeDisabled();
  fireEvent.click(screen.getByLabelText('In-app alerts'));
  await waitFor(() => expect(onPrefs).toHaveBeenCalledWith({ notifications: { in_app: false } }));
});

test('login asks for the emailed code when two-step verification is on', async () => {
  const onAuthenticate = jest.fn().mockResolvedValue({ twoStep: { challenge: 'chal', email: 'as**@example.com' } });
  const onTwoStep = jest.fn().mockResolvedValue('That code is not right.');
  render(<LoginOverlay onAuthenticate={onAuthenticate} onTwoStep={onTwoStep} />);
  fireEvent.change(screen.getByPlaceholderText('you@company.com'), { target: { value: 'asha@example.com' } });
  fireEvent.change(screen.getByPlaceholderText('Your password'), { target: { value: 'secret-123' } });
  fireEvent.click(screen.getByRole('button', { name: 'Log In' }));
  expect(await screen.findByText('Enter your code')).toBeInTheDocument();
  expect(screen.getByText(/as\*\*@example.com/)).toBeInTheDocument();
  fireEvent.change(screen.getByPlaceholderText('123456'), { target: { value: '12a3456' } });
  fireEvent.click(screen.getByRole('button', { name: 'Verify and Log In' }));
  await waitFor(() => expect(onTwoStep).toHaveBeenCalledWith('chal', '123456'));
  expect(await screen.findByText('That code is not right.')).toBeInTheDocument();
});
