jest.mock('../../src/lib/agentStateApi', () => ({
  fetchAgentStates: jest.fn(),
  saveAgentState: jest.fn(),
  deleteAgentState: jest.fn(),
}));

import { act, renderHook } from '@testing-library/react';
import { useState } from 'react';
import { useAgentStatePersistence } from '../../src/hooks/useAgentStatePersistence';
import * as api from '../../src/lib/agentStateApi';
import { legacyKey, secretsKey } from '../../src/lib/agentStateStore';

const mocked = jest.mocked(api);
const EMAIL = 'asha@example.com';

/** Mimics App.tsx: one React state per agent, bound to the persistence hook. */
function useHarness(email: string | undefined) {
  const [capstone, setCapstone] = useState<Record<string, Record<string, unknown>>>({});
  const [aptitude, setAptitude] = useState<Record<string, Record<string, unknown>>>({});
  const [communication, setCommunication] = useState<Record<string, Record<string, unknown>>>({});
  const persistence = useAgentStatePersistence(email, [
    { agentId: 'capstone', states: capstone, merge: setCapstone,
      serialize: (state) => { const { docxFile: _d, zipFile: _z, ...saved } = state; return saved; } },
    { agentId: 'aptitude', states: aptitude, merge: setAptitude },
    { agentId: 'communication', states: communication, merge: setCommunication },
  ]);
  return { capstone, setCapstone, aptitude, setAptitude, communication, setCommunication, ...persistence };
}

const flushPromises = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };
const advance = async (ms: number) => { await act(async () => { jest.advanceTimersByTime(ms); }); await flushPromises(); };

beforeEach(() => {
  jest.useFakeTimers();
  localStorage.clear();
  localStorage.setItem('digidara_token', 'platform-token');
  mocked.fetchAgentStates.mockResolvedValue([]);
  mocked.saveAgentState.mockResolvedValue(undefined);
  mocked.deleteAgentState.mockResolvedValue(undefined);
});
afterEach(() => { jest.useRealTimers(); });

async function loggedIn(email: string | undefined = EMAIL) {
  const view = renderHook(({ address }) => useHarness(address), { initialProps: { address: email } });
  await flushPromises();
  return view;
}

test('loads saved state once and does not upload what it just loaded', async () => {
  mocked.fetchAgentStates.mockResolvedValue([
    { agentId: 'capstone', chatId: 'c1', state: { step: 'awaiting_topic' }, updatedAt: '2026-09-21T00:00:00Z' },
  ]);
  const { result } = await loggedIn();
  expect(mocked.fetchAgentStates).toHaveBeenCalledTimes(1);
  expect(result.current.capstone).toEqual({ c1: { step: 'awaiting_topic' } });
  await advance(2000);
  expect(mocked.saveAgentState).not.toHaveBeenCalled();
  expect(result.current.status).toBe('idle');
});

test('saves only the chat that changed, after a short pause, without agent tokens', async () => {
  mocked.fetchAgentStates.mockResolvedValue([
    { agentId: 'aptitude', chatId: 'a1', state: { step: 'awaiting_mode' }, updatedAt: '2026-09-21T00:00:00Z' },
  ]);
  const { result } = await loggedIn();
  await advance(1000);
  act(() => result.current.setCapstone({ c9: { step: 'grading', thread: 't', token: 'SECRET', sessionToken: 'SECRET2' } }));
  expect(mocked.saveAgentState).not.toHaveBeenCalled(); // debounced
  await advance(900);
  expect(mocked.saveAgentState).toHaveBeenCalledTimes(1);
  expect(mocked.saveAgentState).toHaveBeenCalledWith('platform-token', 'capstone', 'c9', { step: 'grading', thread: 't' }, false);
  expect(JSON.stringify(mocked.saveAgentState.mock.calls)).not.toContain('SECRET');
  // the credentials stay in the browser, per chat, so the chat keeps working after a reload
  expect(JSON.parse(localStorage.getItem(secretsKey(EMAIL))!)).toEqual({ capstone: { c9: { token: 'SECRET', sessionToken: 'SECRET2' } } });
});

test('restores agent tokens from the browser when state is loaded from the server', async () => {
  localStorage.setItem(secretsKey(EMAIL), JSON.stringify({ communication: { m1: { authToken: 'tok' } } }));
  mocked.fetchAgentStates.mockResolvedValue([
    { agentId: 'communication', chatId: 'm1', state: { step: 'main_menu' }, updatedAt: '2026-09-21T00:00:00Z' },
  ]);
  const { result } = await loggedIn();
  expect(result.current.communication.m1).toEqual({ step: 'main_menu', authToken: 'tok' });
  await advance(2000);
  expect(mocked.saveAgentState).not.toHaveBeenCalled();
});

test('a chat removed locally is deleted on the server, others untouched', async () => {
  mocked.fetchAgentStates.mockResolvedValue([
    { agentId: 'capstone', chatId: 'c1', state: { n: 1 }, updatedAt: '2026-09-21T00:00:00Z' },
    { agentId: 'capstone', chatId: 'c2', state: { n: 2 }, updatedAt: '2026-09-21T00:00:00Z' },
  ]);
  const { result } = await loggedIn();
  act(() => result.current.setCapstone(({ c2 }) => ({ c2 })));
  await advance(900);
  expect(mocked.deleteAgentState).toHaveBeenCalledTimes(1);
  expect(mocked.deleteAgentState).toHaveBeenCalledWith('platform-token', 'capstone', 'c1');
  expect(mocked.saveAgentState).not.toHaveBeenCalled();
});

test('nothing is written before the saved state has loaded, and logging out never wipes the server', async () => {
  let release: (value: never[]) => void = () => undefined;
  mocked.fetchAgentStates.mockReturnValue(new Promise((resolve) => { release = resolve as never; }));
  const { result, rerender } = renderHook(({ address }) => useHarness(address), { initialProps: { address: EMAIL as string | undefined } });
  act(() => result.current.setCapstone({ early: { step: 'x' } }));
  await advance(3000);
  expect(mocked.saveAgentState).not.toHaveBeenCalled(); // still loading
  await act(async () => release([]));
  await flushPromises();
  await advance(900);
  expect(mocked.saveAgentState).toHaveBeenCalledTimes(1); // the chat opened while loading is kept and saved

  mocked.saveAgentState.mockClear();
  rerender({ address: undefined }); // logout: states are cleared by the app
  act(() => result.current.setCapstone({}));
  await advance(3000);
  expect(mocked.deleteAgentState).not.toHaveBeenCalled();
});

test('legacy browser state is uploaded once and the local copy is removed only after the server confirms', async () => {
  localStorage.setItem(legacyKey('capstone', EMAIL), JSON.stringify({ old1: { step: 'awaiting_submission', token: 'T' } }));
  localStorage.setItem(legacyKey('aptitude', EMAIL), JSON.stringify({ old2: { step: 'completed' } }));
  mocked.saveAgentState.mockRejectedValueOnce(new TypeError('network down'));
  const { result } = await loggedIn();
  expect(result.current.capstone.old1).toEqual({ step: 'awaiting_submission', token: 'T' }); // visible immediately
  await advance(900);
  expect(result.current.status).toBe('offline');
  expect(localStorage.getItem(legacyKey('capstone', EMAIL))).not.toBeNull(); // nothing confirmed yet: keep the local copy
  expect(localStorage.getItem(legacyKey('aptitude', EMAIL))).not.toBeNull();

  await advance(6000); // retry
  await flushPromises();
  expect(mocked.saveAgentState).toHaveBeenCalledWith('platform-token', 'capstone', 'old1', { step: 'awaiting_submission' }, false);
  expect(mocked.saveAgentState).toHaveBeenCalledWith('platform-token', 'aptitude', 'old2', { step: 'completed' }, false);
  expect(localStorage.getItem(legacyKey('capstone', EMAIL))).toBeNull();
  expect(localStorage.getItem(legacyKey('aptitude', EMAIL))).toBeNull();
  expect(result.current.status).toBe('idle');
});

test('legacy chats the server already has are not overwritten by the older browser copy', async () => {
  localStorage.setItem(legacyKey('capstone', EMAIL), JSON.stringify({ c1: { step: 'old' } }));
  mocked.fetchAgentStates.mockResolvedValue([
    { agentId: 'capstone', chatId: 'c1', state: { step: 'newer' }, updatedAt: '2026-09-21T00:00:00Z' },
  ]);
  const { result } = await loggedIn();
  expect(result.current.capstone.c1).toEqual({ step: 'newer' });
  await advance(2000);
  expect(mocked.saveAgentState).not.toHaveBeenCalled();
  expect(localStorage.getItem(legacyKey('capstone', EMAIL))).toBeNull();
});

test('a failed load shows offline, keeps retrying, and never uploads an empty state', async () => {
  mocked.fetchAgentStates.mockRejectedValueOnce(new TypeError('offline'));
  const { result } = await loggedIn();
  expect(result.current.status).toBe('offline');
  await advance(4000);
  expect(mocked.fetchAgentStates).toHaveBeenCalledTimes(1);
  await advance(2000);
  await flushPromises();
  expect(mocked.fetchAgentStates).toHaveBeenCalledTimes(2);
  expect(result.current.status).toBe('idle');
  expect(mocked.deleteAgentState).not.toHaveBeenCalled();
});

test('shows saving, then offline with a retry, when the server is unreachable', async () => {
  const { result } = await loggedIn();
  await advance(900);
  mocked.saveAgentState.mockRejectedValueOnce(new TypeError('offline'));
  act(() => result.current.setAptitude({ a1: { step: 'awaiting_question' } }));
  await advance(900);
  expect(result.current.status).toBe('offline');
  await advance(5100);
  await flushPromises();
  expect(mocked.saveAgentState).toHaveBeenCalledTimes(2);
  expect(result.current.status).toBe('idle');
});

test('a state the server rejects as too large is not retried forever', async () => {
  const { result } = await loggedIn();
  await advance(900);
  mocked.saveAgentState.mockRejectedValue(Object.assign(new Error('This chat state is too large.'), { status: 422 }));
  act(() => result.current.setCapstone({ big: { step: 'x' } }));
  await advance(900);
  expect(result.current.status).toBe('rejected');
  await advance(60000);
  expect(mocked.saveAgentState).toHaveBeenCalledTimes(1);
});

test('flushNow saves immediately, before the pause elapses', async () => {
  const { result } = await loggedIn();
  await advance(900);
  act(() => result.current.setCapstone({ c1: { step: 'x' } }));
  await act(async () => { await result.current.flushNow(); });
  expect(mocked.saveAgentState).toHaveBeenCalledTimes(1);
});

test('switching to another account never writes the previous account state under the new one', async () => {
  const { result, rerender } = await loggedIn();
  await advance(900);
  act(() => result.current.setCapstone({ mine: { step: 'private' } }));
  await advance(900);
  mocked.saveAgentState.mockClear();
  mocked.deleteAgentState.mockClear();
  mocked.fetchAgentStates.mockResolvedValue([]);
  localStorage.setItem('digidara_token', 'other-token');
  rerender({ address: 'other@example.com' });
  await flushPromises();
  await advance(3000);
  expect(result.current.capstone).toEqual({}); // the previous account's chats are gone from memory
  expect(mocked.saveAgentState).not.toHaveBeenCalled();
  expect(mocked.deleteAgentState).not.toHaveBeenCalled();
});
