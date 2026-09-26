import { buildPendingNotifications, timeLeft, type NotificationSources } from '../../src/lib/notifications';
import type { CapstoneFlowState } from '../../src/lib/capstoneFlow';
import type { Chat } from '../../src/types';

const NOW = Date.parse('2026-09-26T10:00:00Z');
const chat = (id: string, agentId: string, updatedAt = 1): Chat => ({ id, agentId, title: id, messages: [], updatedAt });
const capstone = (over: Partial<CapstoneFlowState>): CapstoneFlowState => ({ step: 'awaiting_submission', name: 'A', email: 'a@x.y', phone: '', difficulty: 'easy', ...over });
const sources = (over: Partial<NotificationSources>): NotificationSources => ({
  chats: [], capstone: {}, codeforge: {}, aptitude: {}, communication: {}, resumeBuilder: {}, certificate: {}, mockInterview: {}, jobFetch: {}, ...over,
});
const bodies = (s: NotificationSources) => buildPendingNotifications(s, NOW).map((n) => n.body);

describe('time left', () => {
  test('is worded in days, hours or minutes, and is null once passed', () => {
    expect(timeLeft('2026-10-03T10:00:00Z', NOW)).toBe('7 days');
    expect(timeLeft('2026-09-29T14:00:00Z', NOW)).toBe('3 days 4 hours');
    expect(timeLeft('2026-09-26T11:00:00Z', NOW)).toBe('1 hour');
    expect(timeLeft('2026-09-26T10:20:00Z', NOW)).toBe('20 minutes');
    expect(timeLeft('2026-09-26T09:00:00Z', NOW)).toBeNull();
    expect(timeLeft('not a date', NOW)).toBeNull();
  });
});

describe('pending notifications', () => {
  test('nothing pending means nothing shown', () => {
    expect(buildPendingNotifications(sources({}), NOW)).toEqual([]);
    expect(bodies(sources({ chats: [chat('c1', 'capstone-project')], capstone: { c1: capstone({ step: 'awaiting_topic_request' }) } }))).toEqual([]);
  });

  test('a capstone project waiting for submission shows the agent, its icon, and the time left', () => {
    const list = buildPendingNotifications(sources({
      chats: [chat('c1', 'capstone-project')],
      capstone: { c1: capstone({ deadlineAt: '2026-10-01T10:00:00Z' }) },
    }), NOW);
    expect(list).toEqual([expect.objectContaining({ chatId: 'c1', agentName: 'Capstone Project Agent', icon: '🎓', body: 'Your project is pending submission — 5 days left.' })]);
  });

  test.each([
    [{ step: 'awaiting_topic_choice' as const }, /Choose project A or B/],
    [{ step: 'awaiting_timer_confirm' as const }, /start your 7-day timer/],
    [{ deadlineAt: '2026-09-25T10:00:00Z' }, /submission window has closed/],
    [{ deadlineAt: '2026-09-27T10:00:00Z', revisionNotes: 'fix it' }, /Revision needed.*1 day left/],
    [{ step: 'awaiting_viva_answer' as const, vivaProgress: '3 of 10' }, /viva is in progress — question 3 of 10/],
    [{ step: 'awaiting_viva_answer' as const, vivaRetryPending: true, vivaAttempt: 1, vivaAttemptsTotal: 3 }, /attempt 2 of 3 is waiting/],
    [{ step: 'graded' as const, passed: true }, /certificate and final report are ready/],
  ])('capstone %#', (over, expected) => {
    expect(bodies(sources({ chats: [chat('c1', 'capstone-project')], capstone: { c1: capstone(over) } }))[0]).toMatch(expected);
  });

  test('a failed grade or an unstarted timer is not a notification', () => {
    expect(bodies(sources({ chats: [chat('c1', 'capstone-project')], capstone: { c1: capstone({ step: 'graded', passed: false }) } }))).toEqual([]);
    expect(bodies(sources({ chats: [chat('c1', 'capstone-project')], capstone: { c1: capstone({}) } }))).toEqual([]);   // no deadline yet
  });

  test('only an agent\'s most recent chat counts', () => {
    const list = buildPendingNotifications(sources({
      chats: [chat('old', 'capstone-project', 1), chat('new', 'capstone-project', 2)],
      capstone: { old: capstone({ step: 'awaiting_timer_confirm' }), new: capstone({ step: 'awaiting_topic_choice' }) },
    }), NOW);
    expect(list.map((n) => n.chatId)).toEqual(['new']);
  });

  test('other agents report their own pending work, each with its own icon', () => {
    const list = buildPendingNotifications(sources({
      chats: [chat('a', 'aptitude'), chat('r', 'resume-builder'), chat('l', 'leetcode')],
      aptitude: { a: { step: 'awaiting_question', testId: 't1' } },
      resumeBuilder: { r: { step: 'completed' } },
      codeforge: { l: { step: 'awaiting_code', problemName: 'Two Sum' } },
    }), NOW);
    expect(list.map((n) => [n.agentName, n.body])).toEqual(expect.arrayContaining([
      ['Aptitude Trainer Agent', 'Your aptitude test is in progress. Continue.'],
      ['Resume Builder Agent', 'Your ATS resume is ready to download.'],
      ['LeetCode / DSA Agent', 'Continue solving “Two Sum”.'],
    ]));
    expect(new Set(list.map((n) => n.icon)).size).toBe(3);
  });

  test('a paused aptitude test says why', () => {
    expect(bodies(sources({ chats: [chat('a', 'aptitude')], aptitude: { a: { step: 'awaiting_next_question', testId: 't', tokenInterrupted: true } } }))[0]).toContain('top up tokens');
  });

  test('chats of a general agent, or with no saved progress, are ignored', () => {
    expect(bodies(sources({ chats: [chat('g', 'career-guide'), chat('c', 'capstone-project')] }))).toEqual([]);
  });
});
