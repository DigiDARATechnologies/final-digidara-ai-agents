jest.mock('../../src/lib/chatApi', () => ({
  fetchChatHistory: jest.fn(),
  syncChatHistory: jest.fn(),
}));

import { act, renderHook } from '@testing-library/react';
import { batchChats, mergeAccountChats, useChats } from '../../src/hooks/useChats';
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
  expect(mocked.syncChatHistory).toHaveBeenCalledWith('token', [chat('c1')], [], false, [], false);
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
  act(() => result.current.saveChats([chat('a', 'changed')]));
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mocked.syncChatHistory).toHaveBeenLastCalledWith('token', [chat('a', 'changed')], [], false, [], false);
});

test('only a chat the learner deleted is sent as deleted, and it stays gone during a load', async () => {
  const { result } = renderHook(() => useChats(EMAIL));
  act(() => result.current.saveChats([chat('a')], ['b']));
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mocked.syncChatHistory).toHaveBeenLastCalledWith('token', [chat('a')], ['b'], false, [], false);
  mocked.fetchChatHistory.mockResolvedValue({ chats: [chat('a'), chat('b')], initialized: true } as never);
  expect((await result.current.refreshAccountChats())?.map((c) => c.id)).toEqual(['a']);
});

test('an edited chat says so; no other save may shorten a chat', async () => {
  const { result } = renderHook(() => useChats(EMAIL));
  act(() => result.current.saveChats([chat('a')], [], false, ['a']));
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mocked.syncChatHistory).toHaveBeenLastCalledWith('token', [chat('a')], [], false, ['a'], false);
  await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); });
  act(() => result.current.saveChats([chat('a', 'next')]));
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mocked.syncChatHistory).toHaveBeenLastCalledWith('token', [chat('a', 'next')], [], false, [], false);
});

test('clearing all history says so, so the server allows it', async () => {
  const { result } = renderHook(() => useChats(EMAIL));
  act(() => result.current.saveChats([], ['a', 'b'], true));
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mocked.syncChatHistory).toHaveBeenLastCalledWith('token', [], ['a', 'b'], true, [], false);
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

describe('saving a large history', () => {
  const flush = async () => { await act(async () => { for (let i = 0; i < 12; i += 1) await Promise.resolve(); }); };
  const sentIds = () => mocked.syncChatHistory.mock.calls.flatMap((call) => (call[1] as { id: string }[]).map((c) => c.id));

  test('a save sends only the chats that changed', async () => {
    mocked.syncChatHistory.mockClear();
    const { result } = renderHook(() => useChats(EMAIL));
    act(() => result.current.saveChats([chat('a'), chat('b')]));
    await flush();
    mocked.syncChatHistory.mockClear();
    act(() => result.current.saveChats([chat('a'), chat('b', 'changed')]));
    await flush();
    expect(sentIds()).toEqual(['b']);
  });

  test('nothing changed: nothing is sent', async () => {
    mocked.syncChatHistory.mockClear();
    const { result } = renderHook(() => useChats(EMAIL));
    act(() => result.current.saveChats([chat('a')]));
    await flush();
    mocked.syncChatHistory.mockClear();
    act(() => result.current.saveChats([chat('a')]));
    await flush();
    expect(mocked.syncChatHistory).not.toHaveBeenCalled();
  });

  test('a batch the server refuses does not stop the other chats being saved', async () => {
    mocked.syncChatHistory.mockClear();
    mocked.syncChatHistory.mockRejectedValueOnce(new Error('Chat history is too large.'));
    const { result } = renderHook(() => useChats(EMAIL));
    const large = [chat('a', 'x'.repeat(3_000_000)), chat('b', 'y'.repeat(3_000_000))];
    act(() => result.current.saveChats(large));
    await flush();
    expect(mocked.syncChatHistory).toHaveBeenCalledTimes(2);
    expect(sentIds()).toEqual(['a', 'b']);
    mocked.syncChatHistory.mockClear();
    // The next save sends again only what did not get through.
    act(() => result.current.saveChats(large));
    await flush();
    expect(sentIds()).toEqual(['a']);
  });

  test('a delete goes with the save, once, even with nothing else to send', async () => {
    mocked.syncChatHistory.mockClear();
    const { result } = renderHook(() => useChats(EMAIL));
    act(() => result.current.saveChats([chat('a')]));
    await flush();
    mocked.syncChatHistory.mockClear();
    act(() => result.current.saveChats([chat('a')], ['gone']));
    await flush();
    expect(mocked.syncChatHistory).toHaveBeenCalledTimes(1);
    expect(mocked.syncChatHistory.mock.calls[0][2]).toEqual(['gone']);
  });

  test('loading sends a large local history in batches and keeps the server list', async () => {
    mocked.syncChatHistory.mockClear();
    mocked.fetchChatHistory.mockResolvedValue({ chats: [], initialized: true } as never);
    mocked.syncChatHistory
      .mockResolvedValueOnce({ chats: [chat('a')], initialized: true } as never)
      .mockResolvedValueOnce({ chats: [chat('a'), chat('b')], initialized: true } as never);
    const { result } = renderHook(() => useChats(EMAIL));
    const loaded = await result.current.loadAccountChats([chat('a', 'x'.repeat(3_000_000)), chat('b', 'y'.repeat(3_000_000))]);
    expect(mocked.syncChatHistory).toHaveBeenCalledTimes(2);
    expect(loaded?.map((c) => c.id)).toEqual(['a', 'b']);
  });

  test('batches stay under the limit and never split or lose a chat', () => {
    const chats = [chat('a', 'x'.repeat(60)), chat('b', 'y'.repeat(60)), chat('c', 'z'.repeat(500))];
    const batches = batchChats(chats, 300);
    expect(batches.flat().map((c) => c.id)).toEqual(['a', 'b', 'c']);
    expect(batches.length).toBeGreaterThan(1);
    expect(batchChats([])).toEqual([]);
  });
});
