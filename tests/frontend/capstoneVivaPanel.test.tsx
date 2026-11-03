const mockSpeak = jest.fn();
jest.mock('../../src/lib/voiceEngine', () => ({
  speakNatural: (...args: unknown[]) => mockSpeak(...args),
  stopSpeaking: jest.fn(),
}));
jest.mock('../../src/lib/orchestratorApi', () => ({ transcribeGeneralAudio: jest.fn() }));
const mockStart = jest.fn();
const mockCancel = jest.fn();
jest.mock('../../src/hooks/useSpeechRecognition', () => ({
  __esModule: true,
  default: () => ({ supported: true, listening: false, transcribing: false, error: '', start: mockStart, stop: jest.fn(), cancel: mockCancel }),
}));
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import CapstoneVivaPanel from '../../src/components/CapstoneVivaPanel';
import type { CapstoneFlowState } from '../../src/lib/capstoneFlow';

const viva: CapstoneFlowState = {
  step: 'awaiting_viva_answer', name: 'Learner', email: 'l@example.test', phone: '', difficulty: 'easy',
  threadId: 'thread', vivaSubmissionId: 'submission', vivaQuestionId: 1, vivaAttempt: 1, vivaAttemptsTotal: 3,
  vivaQuestionText: 'Why did you choose localStorage?', vivaProgress: '2 of 10',
};

beforeEach(() => {
  localStorage.clear();
  mockSpeak.mockReset();
  mockStart.mockReset();
  mockCancel.mockReset();
  mockSpeak.mockImplementation((_text: string, handlers?: { onEnd?: () => void }) => { handlers?.onEnd?.(); return Promise.resolve(true); });
  mockStart.mockReturnValue(true);
});

test('reads the question aloud, then listens and sends after a 5 second pause', async () => {
  const onAnswer = jest.fn();
  render(<CapstoneVivaPanel state={viva} busy={false} onAnswer={onAnswer} onTimeUp={jest.fn()} />);
  expect(mockSpeak).toHaveBeenCalledWith('Why did you choose localStorage?', expect.anything(), true);
  await waitFor(() => expect(mockStart).toHaveBeenCalled());
  expect(mockStart.mock.calls[0][1]).toEqual(expect.objectContaining({ autoStopOnSilence: true, silenceMs: 5000 }));
  act(() => { mockStart.mock.calls[0][0]('It keeps data without a server.', true); });
  expect(onAnswer).toHaveBeenCalledWith('It keeps data without a server.');
});

test('typing takes over from the microphone and is sent with Submit', async () => {
  const onAnswer = jest.fn();
  render(<CapstoneVivaPanel state={viva} busy={false} onAnswer={onAnswer} onTimeUp={jest.fn()} />);
  await waitFor(() => expect(mockStart).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText(/Your answer/), { target: { value: 'Typed answer' } });
  expect(mockCancel).toHaveBeenCalled();
  act(() => { mockStart.mock.calls[0][0]('late voice text', true); });
  expect(onAnswer).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Submit answer' }));
  expect(onAnswer).toHaveBeenCalledWith('Typed answer');
});

test('typing mode neither speaks nor listens', () => {
  localStorage.setItem('digidara_viva_mode', 'typing');
  render(<CapstoneVivaPanel state={{ ...viva, vivaProgress: '1 of 10' }} busy={false} onAnswer={jest.fn()} onTimeUp={jest.fn()} />);
  expect(mockSpeak).not.toHaveBeenCalled();
  expect(mockStart).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('radio', { name: 'Answer by voice' }));
  expect(mockSpeak).toHaveBeenCalled();
  expect(localStorage.getItem('digidara_viva_mode')).toBe('voice');
});

test('shows the 20-minute timer and reports time up once', () => {
  jest.useFakeTimers();
  const onTimeUp = jest.fn();
  render(<CapstoneVivaPanel state={{ ...viva, vivaDeadlineAt: Date.now() + 20 * 60 * 1000 }} busy={false} onAnswer={jest.fn()} onTimeUp={onTimeUp} />);
  expect(screen.getByRole('timer')).toHaveTextContent('20:00');
  act(() => { jest.advanceTimersByTime(20 * 60 * 1000 + 500); });
  expect(onTimeUp).toHaveBeenCalledTimes(1);
  act(() => { jest.advanceTimersByTime(2_000); });
  expect(onTimeUp).toHaveBeenCalledTimes(1);
  jest.useRealTimers();
});

test('the words appear in the answer box while the student is speaking', async () => {
  const onAnswer = jest.fn();
  render(<CapstoneVivaPanel state={viva} busy={false} onAnswer={onAnswer} onTimeUp={jest.fn()} />);
  await waitFor(() => expect(mockStart).toHaveBeenCalled());
  act(() => { mockStart.mock.calls[0][0]('It keeps data', false); });
  expect(screen.getByLabelText(/Your answer/)).toHaveValue('It keeps data');
  expect(onAnswer).not.toHaveBeenCalled();
});

test('the voice or typing choice is asked on the first question only', () => {
  const { rerender } = render(<CapstoneVivaPanel state={{ ...viva, vivaProgress: '1 of 10' }} busy={false} onAnswer={jest.fn()} onTimeUp={jest.fn()} />);
  expect(screen.getByRole('radiogroup')).toBeInTheDocument();
  rerender(<CapstoneVivaPanel state={{ ...viva, vivaQuestionId: 2, vivaProgress: '2 of 10' }} busy={false} onAnswer={jest.fn()} onTimeUp={jest.fn()} />);
  expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();
});

test('the next question is read and the microphone opens with nothing to press', async () => {
  const { rerender } = render(<CapstoneVivaPanel state={viva} busy={false} onAnswer={jest.fn()} onTimeUp={jest.fn()} />);
  await waitFor(() => expect(mockStart).toHaveBeenCalledTimes(1));
  act(() => { mockStart.mock.calls[0][0]('First answer', true); });
  rerender(<CapstoneVivaPanel state={{ ...viva, vivaQuestionId: 2, vivaQuestionText: 'Next question?', vivaProgress: '3 of 10' }} busy={false} onAnswer={jest.fn()} onTimeUp={jest.fn()} />);
  expect(mockSpeak).toHaveBeenLastCalledWith('Next question?', expect.anything(), true);
  await waitFor(() => expect(mockStart).toHaveBeenCalledTimes(2));
});

test('when nothing is heard the microphone reopens by itself, twice', async () => {
  render(<CapstoneVivaPanel state={viva} busy={false} onAnswer={jest.fn()} onTimeUp={jest.fn()} />);
  await waitFor(() => expect(mockStart).toHaveBeenCalledTimes(1));
  act(() => { mockStart.mock.calls[0][0]('', true); });
  act(() => { mockStart.mock.calls[1][0]('', true); });
  expect(mockStart).toHaveBeenCalledTimes(3);
  act(() => { mockStart.mock.calls[2][0]('', true); });
  expect(mockStart).toHaveBeenCalledTimes(3);
  expect(screen.getByText(/No answer was heard/)).toBeInTheDocument();
});

test('an answer that could not be saved leaves the question open to send again', async () => {
  const onAnswer = jest.fn();
  const { rerender } = render(<CapstoneVivaPanel state={viva} busy={false} onAnswer={onAnswer} onTimeUp={jest.fn()} />);
  await waitFor(() => expect(mockStart).toHaveBeenCalled());
  act(() => { mockStart.mock.calls[0][0]('My answer', true); });
  rerender(<CapstoneVivaPanel state={viva} busy onAnswer={onAnswer} onTimeUp={jest.fn()} />);
  rerender(<CapstoneVivaPanel state={viva} busy={false} onAnswer={onAnswer} onTimeUp={jest.fn()} />);
  const submit = screen.getByRole('button', { name: 'Submit answer' });
  expect(submit).toBeEnabled();
  fireEvent.click(submit);
  expect(onAnswer).toHaveBeenCalledTimes(2);
});
