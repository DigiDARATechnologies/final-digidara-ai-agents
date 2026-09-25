import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import MockInterviewPanel from '../../src/components/MockInterviewPanel';
import { downloadMockInterviewReport } from '../../src/lib/mockInterviewApi';
import type { MockInterviewFlowState } from '../../src/lib/mockInterviewFlow';

jest.mock('../../src/hooks/useSpeechRecognition', () => ({
  __esModule: true,
  default: () => ({ supported: false, listening: false, error: '', start: jest.fn(), stop: jest.fn() }),
}));
jest.mock('../../src/lib/mockInterviewApi', () => ({ downloadMockInterviewReport: jest.fn() }));

const live: MockInterviewFlowState = {
  step: 'in_interview', sessionToken: 'session', interviewId: 42,
  question: 'Explain a Python list.', questionOrder: 1, realQuestionIndex: 1,
  totalQuestions: 10, difficulty: 'beginner', roundType: 'technical',
};

beforeEach(() => sessionStorage.clear());

test('live interview shows the question, a 60-second timer, and typed-answer fallback', () => {
  jest.useFakeTimers();
  const onAnswer = jest.fn();
  render(<MockInterviewPanel state={live} busy={false} onAnswer={onAnswer} onExit={jest.fn()} />);
  expect(screen.getByText('Explain a Python list.')).toBeInTheDocument();
  expect(screen.getByText('1.')).toBeInTheDocument();
  expect(screen.getByLabelText('Question 1 of 10')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Replay question' })).not.toBeInTheDocument();
  expect(screen.getByRole('timer')).toHaveTextContent('01:00');
  fireEvent.change(screen.getByLabelText(/your answer/i), { target: { value: 'A mutable sequence.' } });
  act(() => { jest.advanceTimersByTime(5000); });
  expect(screen.getByRole('timer')).toHaveTextContent('00:55');
  fireEvent.click(screen.getByRole('button', { name: 'Submit answer' }));
  expect(onAnswer).toHaveBeenCalledWith('A mutable sequence.', { timeTakenSec: 5, timedOut: false });
  jest.useRealTimers();
});

test('timer expiry submits an unanswered question as timed out', () => {
  jest.useFakeTimers();
  const onAnswer = jest.fn();
  render(<MockInterviewPanel state={live} busy={false} onAnswer={onAnswer} onExit={jest.fn()} />);
  act(() => { jest.advanceTimersByTime(60_250); });
  expect(onAnswer).toHaveBeenCalledWith('', { timeTakenSec: 60, timedOut: true });
  jest.useRealTimers();
});

test('completed interview shows concise summary sections and downloads its PDF', async () => {
  (downloadMockInterviewReport as jest.Mock).mockResolvedValue(undefined);
  const completed: MockInterviewFlowState = {
    ...live, step: 'completed', question: undefined,
    summary: {
      interview_id: 42, overall_score: 8, technical_accuracy: 7,
      communication_clarity: 9, confidence: 8,
      feedback: 'Strong fundamentals. Keep answers concise. Review every missed detail before the next interview.',
      strengths: JSON.stringify(['Python fundamentals']),
      weaknesses: JSON.stringify(['Flask or Django basics']),
      scorecard: [{ question_number: 1, question: 'Explain a Python list.', verdict: 'correct', verdict_reason: 'Clear answer.' }],
    },
  };
  render(<MockInterviewPanel state={completed} busy={false} onAnswer={jest.fn()} onExit={jest.fn()} />);
  for (const label of ['Overall score', 'Knowledge score', 'Communication score', 'Confidence score']) {
    expect(screen.getByText(label)).toBeInTheDocument();
  }
  expect(screen.getByText('Strong fundamentals. Keep answers concise.')).toBeInTheDocument();
  expect(screen.getByText('Strengths')).toBeInTheDocument();
  expect(screen.getByText('Areas to improve')).toBeInTheDocument();
  expect(screen.queryByText(/Review answer feedback/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Clear answer/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Download PDF report' }));
  await waitFor(() => expect(downloadMockInterviewReport).toHaveBeenCalledWith('session', 42));
});

test('completed technical report offers weak-skill practice for reported weak subjects', () => {
  const onPracticeWeakTopics = jest.fn();
  const completed: MockInterviewFlowState = {
    ...live, step: 'completed', question: undefined,
    summary: {
      interview_id: 42, overall_score: 6, technical_accuracy: 5,
      communication_clarity: 8, confidence: 7,
      subject_breakdown: { weak_subjects: ['SQL and relational databases'] },
    },
  };
  render(<MockInterviewPanel state={completed} busy={false} onAnswer={jest.fn()} onExit={jest.fn()} onPracticeWeakTopics={onPracticeWeakTopics} />);
  fireEvent.click(screen.getByRole('button', { name: 'Practice weak skills' }));
  expect(onPracticeWeakTopics).toHaveBeenCalledWith(['SQL and relational databases']);
});
