/** A knowledge test from an assessment link: one question at a time, then the report. */
jest.mock('../../src/lib/knowledgeApi', () => ({
  startKnowledgeAttempt: jest.fn(), submitKnowledgeAnswer: jest.fn(), finishKnowledgeAttempt: jest.fn(),
  downloadKnowledgeReport: jest.fn(),
}));
jest.mock('../../src/lib/voiceEngine', () => ({ speakNatural: jest.fn(() => Promise.resolve()), stopSpeaking: jest.fn() }));
jest.mock('../../src/lib/orchestratorApi', () => ({ transcribeGeneralAudio: jest.fn() }));
// Proctoring has its own tests; here it just shows the test.
jest.mock('../../src/components/ProctorGate', () => ({ __esModule: true, default: ({ children }: { children: unknown }) => children }));

import { act, fireEvent, render, screen } from '@testing-library/react';
import KnowledgeTestView from '../../src/components/KnowledgeTestView';
import * as api from '../../src/lib/knowledgeApi';

const attempt = {
  id: 'a1', status: 'active', title: 'Biology unit 1', question_type: 'mixed', seconds_per_question: 60, answered: [], report: null,
  questions: [
    { id: 'q1', position: 1, qtype: 'mcq', question: 'Where does photosynthesis happen?', options: ['Roots', 'Chloroplasts', 'Nucleus', 'Wall'] },
    { id: 'q2', position: 2, qtype: 'qa', question: 'What does photosynthesis make?', options: [] },
  ],
};
const report = {
  title: 'Biology unit 1', organization: 'Anna University', learner: 'Learner', email: 'l@example.test', finished_at: null,
  score: 1.6, max: 2, percent: 80, integrity: 95, proctor_status: 'completed', summary: 'Well done.', strengths: ['Cells'], improve: ['Energy'],
  rows: [
    { number: 1, qtype: 'mcq', question: 'Where does photosynthesis happen?', options: ['Roots', 'Chloroplasts', 'Nucleus', 'Wall'], your_answer: 'Chloroplasts', correct_answer: 'Chloroplasts', verdict: 'correct', points: 1, feedback: '', explanation: '', time_taken: 5, timed_out: false, answered: true },
    { number: 2, qtype: 'qa', question: 'What does photosynthesis make?', options: [], your_answer: 'Sugar', correct_answer: 'Glucose and oxygen.', verdict: 'partial', points: 0.6, feedback: 'Mention oxygen.', explanation: '', time_taken: 9, timed_out: false, answered: true },
  ],
};

beforeEach(() => {
  jest.clearAllMocks();
  try { localStorage.setItem('digidara_kt_answer_mode', 'typing'); } catch { /* ignore */ }
});

test('the learner answers each question and sees the report', async () => {
  (api.startKnowledgeAttempt as jest.Mock).mockResolvedValue(attempt);
  (api.submitKnowledgeAnswer as jest.Mock).mockResolvedValue({ answered: [] });
  (api.finishKnowledgeAttempt as jest.Mock).mockResolvedValue({ ...attempt, status: 'completed', report });
  await act(async () => { render(<KnowledgeTestView sessionId="s1" title="Biology unit 1" onClose={jest.fn()} />); });

  expect(api.startKnowledgeAttempt).toHaveBeenCalledWith('s1');
  expect(screen.getByText('Where does photosynthesis happen?')).toBeInTheDocument();
  const submit = screen.getByRole('button', { name: 'Submit answer' });
  expect(submit).toBeDisabled();
  fireEvent.click(screen.getByRole('radio', { name: /Chloroplasts/ }));
  await act(async () => { fireEvent.click(submit); });
  expect(api.submitKnowledgeAnswer).toHaveBeenCalledWith('a1', expect.objectContaining({ question_id: 'q1', answer: '1', timed_out: false }));

  expect(screen.getByText('What does photosynthesis make?')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Your answer'), { target: { value: 'Sugar' } });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Submit and finish' })); });
  expect(api.submitKnowledgeAnswer).toHaveBeenLastCalledWith('a1', expect.objectContaining({ question_id: 'q2', answer: 'Sugar' }));
  expect(api.finishKnowledgeAttempt).toHaveBeenCalledWith('a1');

  expect(screen.getByText('80%')).toBeInTheDocument();
  expect(screen.getByText('Well done.')).toBeInTheDocument();
  expect(screen.getByText('Mention oxygen.')).toBeInTheDocument();
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Download PDF report' })); });
  expect(api.downloadKnowledgeReport).toHaveBeenCalledWith({ attemptId: 'a1' }, 'Biology unit 1');
});

test('running out of time sends the answer so far', async () => {
  jest.useFakeTimers();
  try {
    (api.startKnowledgeAttempt as jest.Mock).mockResolvedValue({ ...attempt, seconds_per_question: 20 });
    (api.submitKnowledgeAnswer as jest.Mock).mockResolvedValue({ answered: [] });
    await act(async () => { render(<KnowledgeTestView sessionId="s1" title="Biology unit 1" onClose={jest.fn()} />); });
    await act(async () => { jest.advanceTimersByTime(21_000); });
    expect(api.submitKnowledgeAnswer).toHaveBeenCalledWith('a1', expect.objectContaining({ question_id: 'q1', answer: '', timed_out: true }));
  } finally {
    jest.useRealTimers();
  }
});

test('a test already submitted opens straight to its report', async () => {
  (api.startKnowledgeAttempt as jest.Mock).mockResolvedValue({ ...attempt, status: 'completed', report });
  await act(async () => { render(<KnowledgeTestView sessionId="s1" title="Biology unit 1" onClose={jest.fn()} />); });
  expect(screen.getByText('80%')).toBeInTheDocument();
});
