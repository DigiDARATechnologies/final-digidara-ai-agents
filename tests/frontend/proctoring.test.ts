/** Proctoring rules, assessment links and the assessment's interview start. */
jest.mock('../../src/lib/mockInterviewApi', () => ({
  ensureMockInterviewSession: jest.fn(), getActiveMockInterview: jest.fn(), startMockInterview: jest.fn(),
  submitMockInterviewAnswer: jest.fn(), endMockInterview: jest.fn(), exitMockInterview: jest.fn(),
}));

import * as mockApi from '../../src/lib/mockInterviewApi';
import { linkFromPath } from '../../src/lib/linkPaths';
import { openMockInterviewChat } from '../../src/lib/mockInterviewFlow';
import {
  forgetFreshSession, integrityBand, isFreshSession, levelDifficulty, mockInterviewProctored, resultText, ruleLines,
  setAssessmentLaunch, vivaProctored,
} from '../../src/lib/proctoring';

const user = { id: 'u1', name: 'Prem Kumar', email: 'prem@example.com', mobile: '', initial: 'P' };

test('only Hard and Professional sittings are proctored', () => {
  expect(mockInterviewProctored('advanced')).toBe(true);
  expect(mockInterviewProctored('intermediate')).toBe(false);
  expect(vivaProctored('hard')).toBe(true);
  expect(vivaProctored('professional')).toBe(true);
  expect(vivaProctored('medium')).toBe(false);
  expect(levelDifficulty('professional')).toBe('advanced');
  expect(levelDifficulty('medium')).toBe('intermediate');
});

test('the consent screen lists only the checks that are on', () => {
  const lines = ruleLines({ tab: true, fullscreen: false, copy_paste: false, webcam: false, face: false, max_warnings: 1 });
  expect(lines.join(' ')).toMatch(/Switching tabs/);
  expect(lines.join(' ')).not.toMatch(/camera|full screen\./i);
  expect(lines.at(-1)).toBe('After 1 warning, the next one ends the test.');
});

test('results and integrity read plainly', () => {
  expect(resultText({ score: 7, max: 10 })).toBe('7 / 10');
  expect(resultText({ label: 'Good', passed: true })).toBe('Good (passed)');
  expect(resultText(null)).toBe('-');
  expect(integrityBand(85)).toBe('good');
  expect(integrityBand(60)).toBe('fair');
  expect(integrityBand(20)).toBe('poor');
});

test('assessment links are recognised in the address', () => {
  expect(linkFromPath('/assessment/AbC_def-123456789xyz')).toEqual({ kind: 'assessment', token: 'AbC_def-123456789xyz' });
  expect(linkFromPath('/shared/chat/abcdefghijk')).toEqual({ kind: 'chat', token: 'abcdefghijk' });
  expect(linkFromPath('/assessment/short')).toBeNull();
});

test("an assessment link starts the organization's interview at once", async () => {
  (mockApi.ensureMockInterviewSession as jest.Mock).mockResolvedValue({ sessionToken: 'tok', student_id: 1 });
  (mockApi.getActiveMockInterview as jest.Mock).mockResolvedValue({ active: true, interview_id: 3, question: 'Old', question_order: 2 });
  (mockApi.exitMockInterview as jest.Mock).mockResolvedValue({});
  (mockApi.startMockInterview as jest.Mock).mockResolvedValue({ interview_id: 9, question_order: 1, question: 'What is SQL?', total_questions: 5 });
  setAssessmentLaunch({ sessionId: 'ps1', title: 'Drive round 1', config: { round_type: 'technical', role_name: 'Data Analyst', subject: '', num_questions: 5, level: 'hard' } });

  const { state, messages } = await openMockInterviewChat(user);

  // The practice interview left open is closed first.
  expect(mockApi.exitMockInterview).toHaveBeenCalledWith('tok', 3, 2);
  expect(mockApi.startMockInterview).toHaveBeenCalledWith('tok', expect.objectContaining({
    round_type: 'technical', interview_mode: 'role', role_name: 'Data Analyst', difficulty: 'advanced', num_questions: 5,
  }));
  expect(state).toMatchObject({ step: 'in_interview', interviewId: 9, proctorSessionId: 'ps1', assessmentTitle: 'Drive round 1' });
  expect(messages[0].text).toMatch(/Drive round 1/);
  // The attempt was agreed on the link's page, once.
  expect(isFreshSession('ps1')).toBe(true);
  forgetFreshSession('ps1');
  expect(isFreshSession('ps1')).toBe(false);

  // The next chat is ordinary practice again.
  (mockApi.getActiveMockInterview as jest.Mock).mockResolvedValue({ active: false });
  const next = await openMockInterviewChat(user);
  expect(next.state.step).toBe('choose_round');
});
