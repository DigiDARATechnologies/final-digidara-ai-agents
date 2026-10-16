import { linkFromPath, rememberPendingLink, takePendingLink } from '../../src/lib/linkPaths';

test('Boss links are read from the page path', () => {
  expect(linkFromPath('/shared/chat/abcDEF1234567890')).toEqual({ kind: 'chat', token: 'abcDEF1234567890' });
  expect(linkFromPath('/certificate-link/eyJhbGciOi.eyJ0eXAi.sig-_x')).toEqual({ kind: 'certificate', token: 'eyJhbGciOi.eyJ0eXAi.sig-_x' });
  expect(linkFromPath('/login')).toBeNull();
});

test('a link opened while signed out is kept once, for after sign-in', () => {
  rememberPendingLink({ kind: 'chat', token: 'abcDEF1234567890' });
  expect(takePendingLink()).toEqual({ kind: 'chat', token: 'abcDEF1234567890' });
  expect(takePendingLink()).toBeNull();
});
