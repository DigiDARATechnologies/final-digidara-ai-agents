jest.mock('../../src/lib/chatApi', () => ({
  fetchChatHistory: jest.fn(),
  syncChatHistory: jest.fn(),
}));

import { act, renderHook } from '@testing-library/react';
import { useChats } from '../../src/hooks/useChats';
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
