import { autoChatTitle, formatChatTime, nextChatTitle, type AgentStates } from '../../src/lib/chatTitles';
import type { Agent, Chat } from '../../src/types';

const empty: AgentStates = { aptitude: {}, capstone: {}, certificate: {}, codeforge: {}, communication: {}, mockInterview: {}, resumeBuilder: {} };
const agent = (kind: Agent['kind'], name = 'Some Agent') => ({ id: kind!, name, icon: '', color: '', greeting: '', kind }) as Agent;
const chat = (title: string, extra: Partial<Chat> = {}): Chat => ({
  id: 'c1', agentId: 'x', title, updatedAt: 0,
  messages: [{ role: 'agent', text: 'Hi', time: '' }, { role: 'user', text: title, time: '' }], ...extra,
});

describe('automatic names per agent', () => {
  test('Resume Builder: the target role, then the ATS score', () => {
    const states = { ...empty, resumeBuilder: { c1: { step: 'awaiting_skills', draft: { targetRole: 'python developer' } } } } as AgentStates;
    expect(autoChatTitle(agent('resume-builder'), 'c1', states)).toEqual({ subject: 'Resume · Python developer', result: undefined });
    states.resumeBuilder.c1 = { step: 'reviewing', draft: { targetRole: 'python developer' }, atsScore: 76 } as never;
    expect(autoChatTitle(agent('resume-builder'), 'c1', states)?.result).toBe('ATS 76');
  });

  test('Certification: the exam topic, then the score and pass/fail', () => {
    const states = { ...empty, certificate: { c1: { step: 'awaiting_chat_session', topic: 'Python Programming' } } } as AgentStates;
    expect(autoChatTitle(agent('certificate'), 'c1', states)).toEqual({ subject: 'Python Programming Exam', result: undefined });
    states.certificate.c1 = { step: 'completed', topic: 'Python Programming', score: 76.67, passed: true } as never;
    expect(autoChatTitle(agent('certificate'), 'c1', states)?.result).toBe('76.67% ✓');
    states.certificate.c1 = { step: 'completed', topic: 'Python Exam', score: 40, passed: false } as never;
    expect(autoChatTitle(agent('certificate'), 'c1', states)).toEqual({ subject: 'Python Exam', result: '40% ✗' });
  });

  test('Communication Coach: speaking prompt, writing topic, pronunciation mode', () => {
    const states = { ...empty, communication: { c1: { step: 'speaking_turn', difficulty: 'easy', activeModule: 'speaking', promptText: 'Good evening, Prem! What did you do today that made you happy?' } } } as AgentStates;
    const speaking = autoChatTitle(agent('communication'), 'c1', states)?.subject ?? '';
    expect(speaking.startsWith('🗣️ Speaking · "Good evening, Prem!')).toBe(true);
    expect(speaking.endsWith('…"')).toBe(true);
    states.communication.c1 = { step: 'writing_turn', difficulty: 'easy', activeModule: 'writing', writingTopic: 'My favourite festival' } as never;
    expect(autoChatTitle(agent('communication'), 'c1', states)?.subject).toBe('✍️ Writing · My favourite festival');
  });

  test('Mock Interview: role and level, then the overall score', () => {
    const states = { ...empty, mockInterview: { c1: { step: 'completed', roleName: 'Python Fullstack Developer', difficulty: 'beginner', summary: { overall_score: 7 } } } } as unknown as AgentStates;
    expect(autoChatTitle(agent('mock-interview'), 'c1', states)).toEqual({ subject: 'Interview · Python Fullstack Developer · Beginner', result: '7/10' });
  });

  test('Capstone: the chosen project, then Passed', () => {
    const states = { ...empty, capstone: { c1: { step: 'graded', passed: true, finalScore: 82, chosenTopic: { id: 'A', title: 'Clinic Booking Portal' } } } } as unknown as AgentStates;
    expect(autoChatTitle(agent('capstone'), 'c1', states)).toEqual({ subject: 'Capstone · Clinic Booking Portal', result: 'Passed 82 ✓' });
  });

  test('Aptitude: mode or category, then the score', () => {
    const states = { ...empty, aptitude: { c1: { step: 'completed', mode: 'mixed', score: 7, totalQuestions: 10 } } } as AgentStates;
    expect(autoChatTitle(agent('aptitude'), 'c1', states)).toEqual({ subject: 'Aptitude · Mixed', result: '7/10' });
  });

  test('nothing until the subject is known, and nothing for agents without a flow', () => {
    expect(autoChatTitle(agent('resume-builder'), 'c1', empty)).toBeUndefined();
    expect(autoChatTitle(agent('job-fetch'), 'c1', empty)).toBeUndefined();
    expect(autoChatTitle(undefined, 'c1', empty)).toBeUndefined();
  });
});

describe('when a title changes', () => {
  const resume = agent('resume-builder', 'Resume Builder Agent');
  const auto = { subject: 'Resume · Python Developer' };

  test('a default title (first message or agent name) takes the automatic name', () => {
    expect(nextChatTitle(chat('Create a resume', { titleSource: 'default' }), resume, auto))
      .toEqual({ title: 'Resume · Python Developer', titleSource: 'auto', autoSubject: 'Resume · Python Developer' });
    // Older chats without the marker: still recognised as default.
    expect(nextChatTitle(chat('Create a resume'), resume, auto)?.title).toBe('Resume · Python Developer');
    expect(nextChatTitle({ ...chat('x'), title: 'Resume Builder Agent' }, resume, auto)?.title).toBe('Resume · Python Developer');
  });

  test('a title the user renamed is never changed', () => {
    expect(nextChatTitle(chat('My Infosys resume', { titleSource: 'manual' }), resume, auto)).toBeUndefined();
    // An unknown custom title from before this feature is left alone too.
    expect(nextChatTitle({ ...chat('Create a resume'), title: 'For Infosys' }, resume, auto)).toBeUndefined();
  });

  test('an automatic title only gains a result, and never switches subject', () => {
    const named = chat('Resume · Python Developer', { titleSource: 'auto', autoSubject: 'Resume · Python Developer' });
    expect(nextChatTitle(named, resume, auto)).toBeUndefined();
    expect(nextChatTitle(named, resume, { ...auto, result: 'ATS 76' })?.title).toBe('Resume · Python Developer · ATS 76');
    expect(nextChatTitle(named, resume, { subject: 'Resume · Java Developer' })).toBeUndefined();
  });

  test('an automatic title reloaded from the server (no marker) is still recognised by its subject', () => {
    const reloaded = { ...chat('Create a resume'), title: 'Resume · Python Developer' };
    expect(nextChatTitle(reloaded, resume, { ...auto, result: 'ATS 80' })?.title).toBe('Resume · Python Developer · ATS 80');
  });
});

test('the time under each name reads naturally', () => {
  const now = new Date(2026, 9, 1, 15, 0);
  expect(formatChatTime(new Date(2026, 9, 1, 9, 5).getTime(), now)).toMatch(/^Today, 9:05/);
  expect(formatChatTime(new Date(2026, 8, 30, 19, 2).getTime(), now)).toMatch(/^Yesterday, 7:02/);
  const older = new Date(2026, 8, 20, 10, 0);
  expect(formatChatTime(older.getTime(), now)).toBe(older.toLocaleDateString([], { month: 'short', day: 'numeric' }));
  expect(formatChatTime(new Date(2025, 8, 20, 10, 0).getTime(), now)).toMatch(/2025/);
});
