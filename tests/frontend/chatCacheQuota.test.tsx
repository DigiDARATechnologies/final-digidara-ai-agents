jest.mock('../../src/lib/chatApi', () => ({
  fetchChatHistory: jest.fn(),
  syncChatHistory: jest.fn(),
}));

import { act, renderHook } from '@testing-library/react';
import { mergeAccountChats, useChats } from '../../src/hooks/useChats';
import * as api from '../../src/lib/chatApi';
import { setSessionToken } from '../../src/lib/session';

const mocked = jest.mocked(api);
const EMAIL = 'rubiking@example.com';
const chat = (id: string, text = 'hi') => ({ id, agentId: 'codeforge', title: id, updatedAt: 1, messages: [{ role: 'user', text, time: '' }] }) as never;

function quotaFull() {
  return jest.spyOn(Storage.prototype, 'setItem').mockImplementation((key: string) => {
    if (key.startsWith('digidara_chats_') && !key.includes('server_only')) {
      throw new DOMException("Setting the value of 'digidara_chats_x' exceeded the quota.", 'QuotaExceededError');
    }
  });
}

beforeEach(() => {
  jest.restoreAllMocks();
  localStorage.clear();
  setSessionToken('token');
  mocked.syncChatHistory.mockResolvedValue({ chats: [], initialized: true } as never);
});

test('a full browser storage no longer throws out of saving a chat', async () => {
  const { result } = renderHook(() => useChats(EMAIL));
  quotaFull();
  expect(() => act(() => result.current.saveChats([chat('c1')]))).not.toThrow();
  // The server still receives the chats.
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mocked.syncChatHistory).toHaveBeenCalledWith('token', [chat('c1')], []);
});

test('chats too big for the browser load from the server, never from a partial copy', async () => {
  localStorage.setItem(`digidara_chats_${EMAIL}`, JSON.stringify([chat('old')]));
  const { result } = renderHook(() => useChats(EMAIL));
  const spy = quotaFull();
  act(() => result.current.saveChats([chat('c1', 'x'.repeat(10))]));
  spy.mockRestore();

  expect(localStorage.getItem(`digidara_chats_${EMAIL}`)).toBeNull();
  expect(result.current.loadChats()).toEqual([]);

  mocked.fetchChatHistory.mockResolvedValue({ chats: [chat('server-1')], initialized: true } as never);
  const loaded = await result.current.loadAccountChats([]);
  expect(loaded?.map((c) => c.id)).toEqual(['server-1']);
  // It fits again: the browser copy is back and used.
  expect(result.current.loadChats().map((c) => c.id)).toEqual(['server-1']);
});

test('a save never deletes a chat because it is missing from the list', async () => {
  const { result } = renderHook(() => useChats(EMAIL));
  mocked.fetchChatHistory.mockResolvedValue({ chats: [chat('a'), chat('b'), chat('c')], initialized: true } as never);
  await result.current.loadAccountChats([]);
  // An old list with only one chat in it: the old code told the server to delete the rest.
  act(() => result.current.saveChats([chat('a')]));
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mocked.syncChatHistory).toHaveBeenLastCalledWith('token', [chat('a')], []);
});

test('only a chat the learner deleted is sent as deleted, and it stays gone during a load', async () => {
  const { result } = renderHook(() => useChats(EMAIL));
  act(() => result.current.saveChats([chat('a')], ['b']));
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mocked.syncChatHistory).toHaveBeenLastCalledWith('token', [chat('a')], ['b']);
  mocked.fetchChatHistory.mockResolvedValue({ chats: [chat('a'), chat('b')], initialized: true } as never);
  expect((await result.current.refreshAccountChats())?.map((c) => c.id)).toEqual(['a']);
});

test('an edited chat says so; no other save may shorten a chat', async () => {
  const { result } = renderHook(() => useChats(EMAIL));
  act(() => result.current.saveChats([chat('a')], [], false, ['a']));
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mocked.syncChatHistory).toHaveBeenLastCalledWith('token', [chat('a')], [], false, ['a']);
  await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); });
  act(() => result.current.saveChats([chat('a')]));
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mocked.syncChatHistory).toHaveBeenLastCalledWith('token', [chat('a')], []);
});

test('clearing all history says so, so the server allows it', async () => {
  const { result } = renderHook(() => useChats(EMAIL));
  act(() => result.current.saveChats([], ['a', 'b'], true));
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mocked.syncChatHistory).toHaveBeenLastCalledWith('token', [], ['a', 'b'], true, []);
});

test('saving during a load no longer throws the account history away', async () => {
  const { result } = renderHook(() => useChats(EMAIL));
  let answer: (value: unknown) => void = () => undefined;
  mocked.fetchChatHistory.mockReturnValue(new Promise((resolve) => { answer = resolve; }) as never);
  const loading = result.current.loadAccountChats([]);
  // Auto-naming a chat, or a new chat, during the load: the old code gave up on the history.
  act(() => result.current.saveChats([chat('new')]));
  answer({ chats: [chat('server-1'), chat('server-2')], initialized: true });
  expect((await loading)?.map((c) => c.id)).toEqual(['server-1', 'server-2']);
});

test('a load that fails is asked for again', async () => {
  const { result } = renderHook(() => useChats(EMAIL));
  mocked.fetchChatHistory.mockReset().mockRejectedValueOnce(new Error('502'))
    .mockResolvedValue({ chats: [chat('server-1')], initialized: true } as never);
  expect((await result.current.loadAccountChats([], [1]))?.map((c) => c.id)).toEqual(['server-1']);
  mocked.fetchChatHistory.mockReset().mockRejectedValue(new Error('502'));
  expect(await result.current.loadAccountChats([], [1])).toBeNull();
});

test('merging keeps everything: the account chats, and what changed while they loaded', () => {
  const at = (id: string, updatedAt: number, text = 'hi') => ({ ...(chat(id, text) as object), updatedAt }) as never;
  const old = at('both', 1);
  const changed = at('both', 5, 'newer');
  const server = [at('both', 1, 'server'), at('only-server', 2)];
  const merged = mergeAccountChats([changed, at('new', 6)], server, [old]);
  expect(merged.map((c) => c.id)).toEqual(['both', 'only-server', 'new']);
  expect(merged[0].messages[0].text).toBe('newer');
  // A chat this browser had but the account no longer shows (deleted elsewhere) goes.
  expect(mergeAccountChats([old], server.slice(1), [old]).map((c) => c.id)).toEqual(['only-server']);
});
