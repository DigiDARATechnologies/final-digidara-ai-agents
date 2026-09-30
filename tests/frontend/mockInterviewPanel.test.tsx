import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import MockInterviewPanel from '../../src/components/MockInterviewPanel';
import { downloadMockInterviewReport, transcribeMockInterviewAudio, transcribeMockInterviewPreview } from '../../src/lib/mockInterviewApi';
import type { MockInterviewFlowState } from '../../src/lib/mockInterviewFlow';

const mockSpeechStart = jest.fn();
const mockSpeechStop = jest.fn();
let mockSpeechSupported = false;
let mockSpeechListening = false;
jest.mock('../../src/hooks/useSpeechRecognition', () => ({
  __esModule: true,
  default: () => ({ supported: mockSpeechSupported, listening: mockSpeechListening, error: '', start: mockSpeechStart, stop: mockSpeechStop }),
}));
jest.mock('../../src/lib/mockInterviewApi', () => ({
  downloadMockInterviewReport: jest.fn(),
  transcribeMockInterviewAudio: jest.fn(),
  transcribeMockInterviewPreview: jest.fn(),
}));

const live: MockInterviewFlowState = {
  step: 'in_interview', sessionToken: 'session', interviewId: 42,
  question: 'Explain a Python list.', questionOrder: 1, realQuestionIndex: 1,
  totalQuestions: 10, difficulty: 'beginner', roundType: 'technical',
};

beforeEach(() => {
  sessionStorage.clear();
  mockSpeechSupported = false;
  mockSpeechListening = false;
  mockSpeechStart.mockReset();
  mockSpeechStop.mockReset();
  (transcribeMockInterviewAudio as jest.Mock).mockReset();
});

test('live interview shows the question, a 60-second timer, and typed-answer fallback', async () => {
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
  await waitFor(() => expect(onAnswer).toHaveBeenCalledWith('A mutable sequence.', { timeTakenSec: 5, timedOut: false }));
  jest.useRealTimers();
});

test('timer expiry submits an unanswered question as timed out', async () => {
  jest.useFakeTimers();
  const onAnswer = jest.fn();
  render(<MockInterviewPanel state={live} busy={false} onAnswer={onAnswer} onExit={jest.fn()} />);
  act(() => { jest.advanceTimersByTime(60_250); });
  await waitFor(() => expect(onAnswer).toHaveBeenCalledWith('', { timeTakenSec: 60, timedOut: true }));
  jest.useRealTimers();
});

test('voice answers use contextual audio transcription instead of an inaccurate browser transcript', async () => {
  class FakeMediaRecorder {
    static isTypeSupported = () => true;
    state: RecordingState = 'inactive';
    mimeType = 'audio/webm';
    private listeners = new Map<string, Array<(event: { data: Blob }) => void>>();
    constructor(_stream: MediaStream, _options?: MediaRecorderOptions) {}
    addEventListener(name: string, callback: (event: { data: Blob }) => void) {
      this.listeners.set(name, [...(this.listeners.get(name) || []), callback]);
    }
    start() {
      this.state = 'recording';
      this.listeners.get('start')?.forEach((callback) => callback({ data: new Blob() }));
    }
    stop() {
      this.listeners.get('dataavailable')?.forEach((callback) => callback({ data: new Blob(['recorded voice'], { type: 'audio/webm' }) }));
      this.state = 'inactive';
      this.listeners.get('stop')?.forEach((callback) => callback({ data: new Blob() }));
    }
    pause() {
      this.state = 'paused';
    }
    resume() {
      this.state = 'recording';
    }
  }
  const stopTrack = jest.fn();
  const getUserMedia = jest.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] });
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia },
  });
  Object.defineProperty(window, 'MediaRecorder', { configurable: true, value: FakeMediaRecorder });
  Object.defineProperty(global, 'MediaRecorder', { configurable: true, value: FakeMediaRecorder });
  mockSpeechSupported = true;
  mockSpeechStart.mockImplementation((onTranscript: (text: string) => void) => {
    onTranscript('It is an in the point URL that returns Jason.');
    return true;
  });
  (transcribeMockInterviewAudio as jest.Mock).mockResolvedValue({
    transcript: 'It is an endpoint URL that returns JSON.',
  });
  const onAnswer = jest.fn();

  const { rerender } = render(<MockInterviewPanel state={live} busy={false} onAnswer={onAnswer} onExit={jest.fn()} />);
  await waitFor(() => expect(screen.getByDisplayValue('It is an in the point URL that returns Jason.')).toBeInTheDocument());
  // Pausing browser recognition must pause, rather than finalize, the complete
  // audio capture. Resuming then preserves one blob for enhanced transcription.
  mockSpeechListening = true;
  rerender(<MockInterviewPanel state={live} busy={false} onAnswer={onAnswer} onExit={jest.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: 'Pause microphone' }));
  mockSpeechListening = false;
  rerender(<MockInterviewPanel state={live} busy={false} onAnswer={onAnswer} onExit={jest.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: 'Start microphone' }));
  await waitFor(() => expect(mockSpeechStart).toHaveBeenCalledTimes(2));
  expect(getUserMedia).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Submit answer' }));

  await waitFor(() => expect(transcribeMockInterviewAudio).toHaveBeenCalledWith('session', 42, 1, expect.any(Blob)));
  expect(onAnswer).toHaveBeenCalledWith('It is an endpoint URL that returns JSON.', expect.objectContaining({ timedOut: false }));
  expect(stopTrack).toHaveBeenCalled();
});

test('mobile recording works without browser speech recognition and submits the OpenAI transcript', async () => {
  class FakeMobileMediaRecorder {
    static isTypeSupported = (type: string) => type.startsWith('audio/mp4');
    state: RecordingState = 'inactive';
    mimeType: string;
    private listeners = new Map<string, Array<(event: { data: Blob }) => void>>();
    constructor(_stream: MediaStream, options?: MediaRecorderOptions) {
      this.mimeType = options?.mimeType || 'audio/mp4';
    }
    addEventListener(name: string, callback: (event: { data: Blob }) => void) {
      this.listeners.set(name, [...(this.listeners.get(name) || []), callback]);
    }
    start() {
      this.state = 'recording';
      this.listeners.get('start')?.forEach((callback) => callback({ data: new Blob() }));
    }
    stop() {
      this.listeners.get('dataavailable')?.forEach((callback) => callback({
        data: new Blob(['mobile voice'], { type: 'audio/mp4' }),
      }));
      this.state = 'inactive';
      this.listeners.get('stop')?.forEach((callback) => callback({ data: new Blob() }));
    }
  }
  const stopTrack = jest.fn();
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: jest.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] }) },
  });
  Object.defineProperty(window, 'MediaRecorder', { configurable: true, value: FakeMobileMediaRecorder });
  Object.defineProperty(global, 'MediaRecorder', { configurable: true, value: FakeMobileMediaRecorder });
  mockSpeechSupported = false;
  (transcribeMockInterviewAudio as jest.Mock).mockResolvedValue({
    transcript: 'A Python list is a mutable ordered collection.',
  });
  const onAnswer = jest.fn();

  render(<MockInterviewPanel state={live} busy={false} onAnswer={onAnswer} onExit={jest.fn()} />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Pause microphone' })).toBeEnabled());
  expect(screen.getByRole('button', { name: 'Submit answer' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Submit answer' }));

  await waitFor(() => expect(transcribeMockInterviewAudio).toHaveBeenCalledWith('session', 42, 1, expect.any(Blob)));
  expect(onAnswer).toHaveBeenCalledWith('A Python list is a mutable ordered collection.', expect.objectContaining({ timedOut: false }));
  expect(stopTrack).toHaveBeenCalled();
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
  expect(screen.getByText('Areas to Improve')).toBeInTheDocument();
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
  fireEvent.click(screen.getByRole('button', { name: 'Practice Weak Skills' }));
  expect(onPracticeWeakTopics).toHaveBeenCalledWith(['SQL and relational databases']);
});

describe('on a phone', () => {
  const realUserAgent = navigator.userAgent;
  class FakePhoneRecorder {
    static isTypeSupported = () => true;
    state: RecordingState = 'inactive';
    mimeType = 'audio/mp4';
    private listeners = new Map<string, Array<(event: { data: Blob }) => void>>();
    constructor(_stream: MediaStream, _options?: MediaRecorderOptions) {}
    addEventListener(name: string, callback: (event: { data: Blob }) => void) {
      this.listeners.set(name, [...(this.listeners.get(name) || []), callback]);
    }
    start() {
      this.state = 'recording';
      this.listeners.get('start')?.forEach((callback) => callback({ data: new Blob() }));
    }
    stop() {
      this.listeners.get('dataavailable')?.forEach((callback) => callback({ data: new Blob(['phone voice'], { type: 'audio/mp4' }) }));
      this.state = 'inactive';
      this.listeners.get('stop')?.forEach((callback) => callback({ data: new Blob() }));
    }
  }

  beforeEach(() => {
    Object.defineProperty(navigator, 'userAgent', { configurable: true, get: () => 'Mozilla/5.0 (Linux; Android 14) Chrome/128.0 Mobile Safari/537.36' });
    Object.defineProperty(window, 'MediaRecorder', { configurable: true, value: FakePhoneRecorder });
    Object.defineProperty(global, 'MediaRecorder', { configurable: true, value: FakePhoneRecorder });
    mockSpeechSupported = true;
  });

  afterEach(() => {
    Object.defineProperty(navigator, 'userAgent', { configurable: true, get: () => realUserAgent });
  });

  test('only the recorder uses the microphone, and the recording is transcribed on submit', async () => {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: jest.fn().mockResolvedValue({ getTracks: () => [{ stop: jest.fn() }] }) },
    });
    (transcribeMockInterviewAudio as jest.Mock).mockResolvedValue({ transcript: 'A list is a mutable sequence.' });
    const onAnswer = jest.fn();
    render(<MockInterviewPanel state={live} busy={false} onAnswer={onAnswer} onExit={jest.fn()} />);
    await waitFor(() => expect(screen.getByText(/Recording your answer - press Submit when you finish/)).toBeInTheDocument());
    // The browser recognizer would compete with the recorder for the microphone.
    expect(mockSpeechStart).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Submit answer' }));
    await waitFor(() => expect(onAnswer).toHaveBeenCalledWith('A list is a mutable sequence.', expect.objectContaining({ timedOut: false })));
  });

  test('a blocked microphone says why, not just "unavailable"', async () => {
    mockSpeechSupported = false;
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: jest.fn().mockRejectedValue(Object.assign(new Error('denied'), { name: 'NotAllowedError' })) },
    });
    render(<MockInterviewPanel state={live} busy={false} onAnswer={jest.fn()} onExit={jest.fn()} />);
    await waitFor(() => expect(screen.getByText(/Microphone permission was denied/)).toBeInTheDocument());
    expect(screen.getByText(/You can also type your answer below/)).toBeInTheDocument();
  });
});

describe('silence handling and live text on a phone', () => {
  const realUserAgent = navigator.userAgent;
  let micLevel = 0;

  class FakeAudioContext {
    state = 'running';
    resume() { return Promise.resolve(); }
    close() { this.state = 'closed'; return Promise.resolve(); }
    createMediaStreamSource() { return { connect: () => undefined }; }
    createAnalyser() {
      return {
        fftSize: 1024,
        getByteTimeDomainData(samples: Uint8Array) {
          const amplitude = Math.round(micLevel * 128);
          samples.forEach((_, index) => { samples[index] = 128 + (index % 2 ? amplitude : -amplitude); });
        },
      };
    }
  }

  class ChunkingRecorder {
    static isTypeSupported = () => true;
    state: RecordingState = 'inactive';
    mimeType = 'audio/mp4';
    private listeners = new Map<string, Array<(event: { data: Blob }) => void>>();
    private timer: number | undefined;
    constructor(_stream: MediaStream, _options?: MediaRecorderOptions) {}
    addEventListener(name: string, callback: (event: { data: Blob }) => void) {
      this.listeners.set(name, [...(this.listeners.get(name) || []), callback]);
    }
    private emit(name: string, data = new Blob()) {
      this.listeners.get(name)?.forEach((callback) => callback({ data }));
    }
    start() {
      this.state = 'recording';
      this.emit('start');
      this.timer = window.setInterval(() => this.emit('dataavailable', new Blob(['voice'], { type: 'audio/mp4' })), 250);
    }
    stop() {
      window.clearInterval(this.timer);
      this.emit('dataavailable', new Blob(['voice'], { type: 'audio/mp4' }));
      this.state = 'inactive';
      this.emit('stop');
    }
    pause() { this.state = 'paused'; }
    resume() { this.state = 'recording'; }
  }

  async function advance(ms: number) {
    await act(async () => { jest.advanceTimersByTime(ms); });
  }

  beforeEach(() => {
    jest.useFakeTimers();
    micLevel = 0;
    Object.defineProperty(navigator, 'userAgent', { configurable: true, get: () => 'Mozilla/5.0 (Linux; Android 14) Chrome/128.0 Mobile Safari/537.36' });
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: jest.fn().mockResolvedValue({ getTracks: () => [{ stop: jest.fn() }] }) },
    });
    Object.defineProperty(window, 'MediaRecorder', { configurable: true, value: ChunkingRecorder });
    Object.defineProperty(global, 'MediaRecorder', { configurable: true, value: ChunkingRecorder });
    Object.defineProperty(window, 'AudioContext', { configurable: true, value: FakeAudioContext });
    (transcribeMockInterviewPreview as jest.Mock).mockReset().mockResolvedValue({ transcript: 'A view function handles a route' });
  });

  afterEach(() => {
    jest.useRealTimers();
    Object.defineProperty(navigator, 'userAgent', { configurable: true, get: () => realUserAgent });
    delete (window as { AudioContext?: unknown }).AudioContext;
  });

  async function startRecording(onAnswer = jest.fn(), onExit = jest.fn()) {
    render(<MockInterviewPanel state={live} busy={false} onAnswer={onAnswer} onExit={onExit} />);
    await advance(0);
    await waitFor(() => expect(screen.getByText(/Recording your answer/)).toBeInTheDocument());
    return { onAnswer, onExit };
  }

  test('the answer appears in the box while speaking, and a 5 second pause submits it', async () => {
    (transcribeMockInterviewAudio as jest.Mock).mockResolvedValue({ transcript: 'A view function handles a route and returns a response.' });
    const { onAnswer } = await startRecording();
    micLevel = 0.2;
    await advance(1_000);
    expect(transcribeMockInterviewPreview).toHaveBeenCalledWith('session', 42, 1, expect.any(Blob));
    await waitFor(() => expect(screen.getByDisplayValue('A view function handles a route')).toBeInTheDocument());
    expect(onAnswer).not.toHaveBeenCalled();

    micLevel = 0;
    await advance(3_000);
    expect(screen.getByText(/Pause detected - submitting your answer in/)).toBeInTheDocument();
    expect(onAnswer).not.toHaveBeenCalled();
    await advance(2_500);
    await waitFor(() => expect(onAnswer).toHaveBeenCalledWith('A view function handles a route and returns a response.', expect.objectContaining({ timedOut: false })));
  });

  test('without speech, "Hey, are you there?" is asked at 30s and the interview ends 15s later', async () => {
    const { onAnswer, onExit } = await startRecording();
    await advance(29_000);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    await advance(1_500);
    expect(screen.getByRole('alert')).toHaveTextContent('Hey, are you there?');
    await advance(14_000);
    expect(onExit).not.toHaveBeenCalled();
    await advance(1_500);
    expect(onExit).toHaveBeenCalledWith('inactive');
    expect(onAnswer).not.toHaveBeenCalled();
  });

  test('speaking after the prompt clears it and the answer carries on normally', async () => {
    const { onExit } = await startRecording();
    await advance(30_500);
    expect(screen.getByRole('alert')).toHaveTextContent('Hey, are you there?');
    micLevel = 0.2;
    await advance(500);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    await advance(20_000);
    expect(onExit).not.toHaveBeenCalled();
  });

  test('typing an answer turns the automatic rules off', async () => {
    const { onAnswer, onExit } = await startRecording();
    fireEvent.change(screen.getByLabelText(/your answer/i), { target: { value: 'I am typing it' } });
    await advance(50_000);
    expect(onExit).not.toHaveBeenCalled();
    expect(onAnswer).not.toHaveBeenCalled();
  });
  test('live text still works when the phone keeps the volume meter suspended, and new words count as speech', async () => {
    class SuspendedAudioContext extends FakeAudioContext {
      state = 'suspended';
      resume() { return Promise.resolve(); }
    }
    Object.defineProperty(window, 'AudioContext', { configurable: true, value: SuspendedAudioContext });
    (transcribeMockInterviewPreview as jest.Mock).mockReset()
      .mockResolvedValueOnce({ transcript: 'A view' })
      .mockResolvedValue({ transcript: 'A view function handles a route' });
    (transcribeMockInterviewAudio as jest.Mock).mockResolvedValue({ transcript: 'A view function handles a route.' });
    const { onAnswer } = await startRecording();

    await advance(1_000);
    await waitFor(() => expect(screen.getByDisplayValue('A view')).toBeInTheDocument());
    await advance(3_000);
    await waitFor(() => expect(screen.getByDisplayValue('A view function handles a route')).toBeInTheDocument());
    // The text stopped growing: that is the pause, even though the meter hears nothing.
    expect(onAnswer).not.toHaveBeenCalled();
    await advance(6_000);
    await waitFor(() => expect(onAnswer).toHaveBeenCalledWith('A view function handles a route.', expect.objectContaining({ timedOut: false })));
  });

  test('a speechSynthesis "speaking" flag stuck at true (Android Chrome) does not silence the meter', async () => {
    Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: { speaking: true, cancel: jest.fn() } });
    try {
      await startRecording();
      micLevel = 0.2;
      await advance(1_000);
      expect(transcribeMockInterviewPreview).toHaveBeenCalled();
      await waitFor(() => expect(screen.getByDisplayValue('A view function handles a route')).toBeInTheDocument());
    } finally {
      delete (window as { speechSynthesis?: unknown }).speechSynthesis;
    }
  });

  test('repeated live-text failures are shown instead of failing silently', async () => {
    (transcribeMockInterviewPreview as jest.Mock).mockReset().mockRejectedValue(new Error('Agent did not respond'));
    await startRecording();
    micLevel = 0.2;
    await advance(4_000);
    await waitFor(() => expect(screen.getByText(/Live text isn't available right now \(Agent did not respond\)/)).toBeInTheDocument());
    expect(screen.getByText(/still turned into text when you submit/)).toBeInTheDocument();
  });
});
