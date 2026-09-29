import { act, renderHook } from '@testing-library/react';
import useSpeechRecognition from '../../src/hooks/useSpeechRecognition';

type ResultCallback = ((event: {
  resultIndex: number;
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string; confidence: number } }>;
}) => void) | null;

class FakeSpeechRecognition {
  static latest: FakeSpeechRecognition | null = null;
  lang = '';
  interimResults = false;
  continuous = false;
  onresult: ResultCallback = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  onstart: (() => void) | null = null;
  startCount = 0;

  constructor() {
    FakeSpeechRecognition.latest = this;
  }

  start() {
    this.startCount += 1;
    this.onstart?.();
  }

  stop() {
    this.onend?.();
  }

  abort() {
    this.onend?.();
  }

  result(text: string) {
    this.onresult?.({
      resultIndex: 0,
      results: [{ isFinal: true, 0: { transcript: text, confidence: 1 } }],
    });
  }
}

beforeEach(() => {
  jest.useFakeTimers();
  FakeSpeechRecognition.latest = null;
  Object.defineProperty(window, 'webkitSpeechRecognition', {
    configurable: true,
    value: FakeSpeechRecognition,
  });
});

afterEach(() => {
  jest.useRealTimers();
  delete window.webkitSpeechRecognition;
});

test('restarts after a browser-ended session and keeps the complete answer until explicitly stopped', () => {
  const onResult = jest.fn();
  const { result } = renderHook(() => useSpeechRecognition());

  act(() => {
    expect(result.current.start(onResult)).toBe(true);
  });
  const recognition = FakeSpeechRecognition.latest!;
  expect(result.current.listening).toBe(true);

  act(() => {
    recognition.result('Application Programming Interface');
    recognition.onend?.();
    jest.advanceTimersByTime(150);
  });
  expect(recognition.startCount).toBe(2);
  expect(result.current.listening).toBe(true);

  act(() => {
    recognition.result('connects software systems');
    result.current.stop();
  });

  expect(onResult).toHaveBeenLastCalledWith(
    'Application Programming Interface connects software systems',
    true,
  );
  expect(result.current.listening).toBe(false);
});
