import { diffStates, legacyKey, mergeSecrets, readLegacyStates, secretsKey, splitSecrets } from '../../src/lib/agentStateStore';

const identity = (_agent: string, state: Record<string, unknown>) => state;

test('agent session tokens are separated from the state that is stored', () => {
  const { clean, secrets } = splitSecrets({ step: 'x', sessionToken: 'a', authToken: 'b', token: 'c', keep: 1 });
  expect(clean).toEqual({ step: 'x', keep: 1 });
  expect(secrets).toEqual({ sessionToken: 'a', authToken: 'b', token: 'c' });
  expect(mergeSecrets(clean, secrets)).toEqual({ step: 'x', keep: 1, sessionToken: 'a', authToken: 'b', token: 'c' });
  expect(mergeSecrets(clean, undefined)).toEqual(clean);
});

test('non-string or empty tokens are dropped rather than stored', () => {
  expect(splitSecrets({ token: '', sessionToken: 5 }).clean).toEqual({});
});

test('a diff lists only changed and removed chats', () => {
  const snapshot = { capstone: { c1: JSON.stringify({ n: 1 }), c2: JSON.stringify({ n: 2 }) } };
  const { changes, removals } = diffStates(snapshot, { capstone: { c1: { n: 1 }, c3: { n: 3 } } }, identity);
  expect(changes.map((c) => `${c.agentId}:${c.chatId}`)).toEqual(['capstone:c3']);
  expect(removals).toEqual([{ agentId: 'capstone', chatId: 'c2' }]);
});

test('a token changing alone does not cause an upload', () => {
  const snapshot = { communication: { m1: JSON.stringify({ step: 'menu' }) } };
  const { changes, secrets } = diffStates(snapshot, { communication: { m1: { step: 'menu', authToken: 'fresh' } } }, identity);
  expect(changes).toEqual([]);
  expect(secrets).toEqual({ communication: { m1: { authToken: 'fresh' } } });
});

test('the serializer can drop what cannot be stored', () => {
  const drop = (_agent: string, state: Record<string, unknown>) => { const { file: _f, ...rest } = state; return rest; };
  const { changes } = diffStates({}, { capstone: { c1: { step: 'x', file: {} } } }, drop);
  expect(changes[0].state).toEqual({ step: 'x' });
});

test('legacy browser keys keep their original names and tolerate corrupt data', () => {
  expect(legacyKey('resume_builder', ' Asha@Example.com ')).toBe('digidara_resume_builder_asha@example.com');
  expect(legacyKey('job_fetch', 'a@b.com')).toBe('digidara_job_fetch_a@b.com');
  expect(secretsKey('A@B.com')).toBe('digidara_agent_secrets_a@b.com');
  localStorage.setItem(legacyKey('capstone', 'a@b.com'), '{not json');
  expect(readLegacyStates('capstone', 'a@b.com')).toEqual({});
  localStorage.setItem(legacyKey('capstone', 'a@b.com'), '[1,2]');
  expect(readLegacyStates('capstone', 'a@b.com')).toEqual({});
});
