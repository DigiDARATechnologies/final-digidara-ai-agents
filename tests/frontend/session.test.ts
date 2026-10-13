import { onSessionSwitched, sessionToken, setSessionToken } from '../../src/lib/session';

function otherTabWrites(value: string | null) {
  const oldValue = localStorage.getItem('digidara_token');
  if (value === null) localStorage.removeItem('digidara_token');
  else localStorage.setItem('digidara_token', value);
  window.dispatchEvent(new StorageEvent('storage', { key: 'digidara_token', oldValue, newValue: value }));
}

beforeEach(() => setSessionToken('token-a'));

test('a sign-in to another account in another tab switches this tab and stops its saves', () => {
  const onSwitch = jest.fn();
  const stop = onSessionSwitched(onSwitch);
  expect(sessionToken()).toBe('token-a');
  otherTabWrites('token-b');
  // The old tab no longer hands out any token, so nothing is saved into account B.
  expect(sessionToken()).toBeNull();
  expect(onSwitch).toHaveBeenCalledWith(false);
  stop();
});

test('a sign-out in another tab signs this tab out too', () => {
  const onSwitch = jest.fn();
  const stop = onSessionSwitched(onSwitch);
  otherTabWrites(null);
  expect(sessionToken()).toBeNull();
  expect(onSwitch).toHaveBeenCalledWith(true);
  stop();
});

test('this tab signing in again is not a switch', () => {
  const onSwitch = jest.fn();
  const stop = onSessionSwitched(onSwitch);
  setSessionToken('token-c');
  window.dispatchEvent(new StorageEvent('storage', { key: 'digidara_token', newValue: 'token-c' }));
  expect(sessionToken()).toBe('token-c');
  expect(onSwitch).not.toHaveBeenCalled();
  stop();
});
