jest.mock('../../src/lib/capstoneApi', () => ({}));

import type { RegradeOffer } from '../../src/lib/capstoneApi';
import { regradeMessage, reopenForRegrade, type CapstoneFlowState } from '../../src/lib/capstoneFlow';
import { regradeNotifications } from '../../src/lib/notifications';

const offer: RegradeOffer = {
  thread_id: 'thread-1', title: 'To-Do App', chosen_topic: null, requirements: { a: 1 }, deadline_at: '2026-01-01T00:00:00+00:00',
  score: 70, passed: true, chances_left: 3,
};
const graded = { step: 'graded', name: 'H', email: 'h@example.com', phone: '', difficulty: 'easy', threadId: 'thread-1', passed: true, finalScore: 70, vivaSubmissionId: 's1', revisionNotes: 'old' } as CapstoneFlowState;

test('the bell says what happened and how many chances are left, and comes back when that changes', () => {
  const [note] = regradeNotifications([offer]);
  expect(note.body).toBe('To-Do App (70/100): a problem on our side may have lowered this grade. You have 3 chances to submit it again.');
  expect(note.chatId).toBe('');
  expect(note.id).toBe('thread-1');
  const [later] = regradeNotifications([{ ...offer, chances_left: 1 }]);
  expect(later.key).not.toBe(note.key);
  expect(later.body).toContain('1 chance to');
});

test('opening a chance reopens the project for upload and keeps the earlier result', () => {
  const open = reopenForRegrade(graded, offer);
  expect(open).toMatchObject({ step: 'awaiting_submission', threadId: 'thread-1', finalScore: 70, vivaSubmissionId: 's1', revisionNotes: null, requirements: { a: 1 } });
});

test('a project whose chat is gone reopens from the offer', () => {
  const open = reopenForRegrade({ step: 'awaiting_topic_request', name: 'H', email: 'h@example.com', phone: '', difficulty: 'easy' } as CapstoneFlowState, offer);
  expect(open).toMatchObject({ step: 'awaiting_submission', threadId: 'thread-1', deadlineAt: offer.deadline_at });
});

test('the message promises a passed student their pass, and only them', () => {
  expect(regradeMessage(offer)).toContain('Your earlier pass stays safe');
  expect(regradeMessage({ ...offer, passed: false })).not.toContain('Your earlier pass');
  expect(regradeMessage(offer)).toContain('even if your 7-day window has closed');
});
