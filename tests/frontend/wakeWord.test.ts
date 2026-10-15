import { matchWake } from '../../src/lib/wakeWord';

test('the wake words are found, with what follows them', () => {
  expect(matchWake('hey boss')).toEqual({ rest: '' });
  expect(matchWake('Hey Boss, what is this error?')).toEqual({ rest: 'what is this error?' });
  expect(matchWake('okay boss help me')).toEqual({ rest: 'help me' });
  expect(matchWake('hey bus how do I start')).toEqual({ rest: 'how do I start' });
});

test('talk that is not the wake words is ignored', () => {
  expect(matchWake('the boss said hello')).toBeNull();
  expect(matchWake('hey there')).toBeNull();
  expect(matchWake('bossy')).toBeNull();
});
