import { act, renderHook, waitFor } from '@testing-library/react';
import useSpeechRecognition from '../../src/hooks/useSpeechRecognition';
import { isMobileVoiceDevice, microphoneErrorMessage } from '../../src/lib/voiceCapture';

const ANDROID = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36';
const DESKTOP = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36';

class FakeRecorder {
  static isTypeSupported = (type: string) => type.startsWith('audio/webm');
  static latest: FakeRecorder | null = null;
  state: RecordingState = 'inactive';
  mimeType: string;
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  private stopListeners: Array<() => void> = [];
  constructor(_stream: MediaStream, options?: MediaRecorderOptions) {
    this.mimeType = options?.mimeType ?? 'audio/webm';
    FakeRecorder.latest = this;
  }
  addEventListener(name: string, callback: () => void) {
    if (name === 'stop') this.stopListeners.push(callback);
  }
  start() {
    this.state = 'recording';
  }
  stop() {
    this.ondataavailable?.({ data: new Blob(['spoken answer'], { type: this.mimeType }) });
    this.state = 'inactive';
    this.stopListeners.forEach((callback) => callback());
  }
}

class FakeSpeechRecognition {
  static created = 0;
  lang = '';
  interimResults = false;
  continuous = false;
  onresult = null;
  onerror = null;
  onend = null;
  onstart: (() => void) | null = null;
  constructor() {
    FakeSpeechRecognition.created += 1;
  }
  start() {
    this.onstart?.();
  }
  stop() {}
  abort() {}
}

let getUserMedia: jest.Mock;
const stopTrack = jest.fn();

function setUserAgent(value: string) {
  Object.defineProperty(navigator, 'userAgent', { configurable: true, get: () => value });
}

beforeEach(() => {
  setUserAgent(ANDROID);
  FakeRecorder.latest = null;
  FakeSpeechRecognition.created = 0;
  stopTrack.mockReset();
  getUserMedia = jest.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] });
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } });
  Object.defineProperty(window, 'MediaRecorder', { configurable: true, value: FakeRecorder });
  Object.defineProperty(global, 'MediaRecorder', { configurable: true, value: FakeRecorder });
  Object.defineProperty(window, 'webkitSpeechRecognition', { configurable: true, value: FakeSpeechRecognition });
});

afterEach(() => {
  setUserAgent(DESKTOP);
  delete (window as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition;
});

test('phones and tablets are detected, desktops are not', () => {
  expect(isMobileVoiceDevice()).toBe(true);
  setUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1');
  expect(isMobileVoiceDevice()).toBe(true);
  setUserAgent(DESKTOP);
  expect(isMobileVoiceDevice()).toBe(false);
});

test('on a phone with a transcriber, the answer is recorded on one stream and transcribed by the server when it stops', async () => {
  const transcribe = jest.fn().mockResolvedValue('I enjoy reading books');
  const onResult = jest.fn();
  const { result } = renderHook(() => useSpeechRecognition('en-US', transcribe));
  expect(result.current.recordingMode).toBe(true);
  expect(result.current.supported).toBe(true);

  act(() => { result.current.start(onResult); });
  await waitFor(() => expect(FakeRecorder.latest?.state).toBe('recording'));
  // The browser recognizer never runs next to the recorder on a phone.
  expect(FakeSpeechRecognition.created).toBe(0);
  expect(getUserMedia).toHaveBeenCalledTimes(1);
  expect(result.current.listening).toBe(true);

  act(() => { result.current.stop(); });
  await waitFor(() => expect(onResult).toHaveBeenCalledWith('I enjoy reading books', true));
  expect(transcribe.mock.calls[0][0]).toBeInstanceOf(Blob);
  expect(transcribe.mock.calls[0][0].type).toBe('audio/webm;codecs=opus');
  expect(stopTrack).toHaveBeenCalled();
  expect(result.current.listening).toBe(false);
  expect(result.current.transcribing).toBe(false);
  expect(result.current.error).toBe('');
});

test('a denied microphone explains what to do instead of failing silently', async () => {
  getUserMedia.mockRejectedValue(Object.assign(new Error('denied'), { name: 'NotAllowedError' }));
  const { result } = renderHook(() => useSpeechRecognition('en-US', jest.fn()));
  act(() => { result.current.start(jest.fn()); });
  await waitFor(() => expect(result.current.error).toContain('Microphone permission was denied'));
  expect(result.current.error).toContain('browser settings');
  expect(result.current.listening).toBe(false);
});

test('a failed transcription says why and leaves the text empty', async () => {
  const onResult = jest.fn();
  const { result } = renderHook(() => useSpeechRecognition('en-US', jest.fn().mockRejectedValue(new Error('Audio transcription is temporarily unavailable'))));
  act(() => { result.current.start(onResult); });
  await waitFor(() => expect(FakeRecorder.latest?.state).toBe('recording'));
  act(() => { result.current.stop(); });
  await waitFor(() => expect(onResult).toHaveBeenCalledWith('', true));
  expect(result.current.error).toContain('temporarily unavailable');
  expect(result.current.error).toContain('Tap the microphone to try again');
});

test('unmounting mid-recording throws the recording away instead of transcribing it', async () => {
  const transcribe = jest.fn();
  const { result, unmount } = renderHook(() => useSpeechRecognition('en-US', transcribe));
  act(() => { result.current.start(jest.fn()); });
  await waitFor(() => expect(FakeRecorder.latest?.state).toBe('recording'));
  unmount();
  expect(FakeRecorder.latest?.state).toBe('inactive');
  expect(transcribe).not.toHaveBeenCalled();
  expect(stopTrack).toHaveBeenCalled();
});

test('without a transcriber, or on a desktop, the browser recognizer is used exactly as before', () => {
  const phoneWithout = renderHook(() => useSpeechRecognition('en-US'));
  expect(phoneWithout.result.current.recordingMode).toBe(false);
  act(() => { phoneWithout.result.current.start(jest.fn()); });
  expect(FakeSpeechRecognition.created).toBe(1);

  setUserAgent(DESKTOP);
  const desktop = renderHook(() => useSpeechRecognition('en-US', jest.fn()));
  expect(desktop.result.current.recordingMode).toBe(false);
  act(() => { desktop.result.current.start(jest.fn()); });
  expect(FakeSpeechRecognition.created).toBe(2);
  expect(getUserMedia).not.toHaveBeenCalled();
});

test.each([
  ['NotFoundError', 'No microphone was found'],
  ['NotReadableError', 'being used by another app'],
  ['SomethingElse', 'could not start'],
])('microphone error %s is explained', (name, text) => {
  expect(microphoneErrorMessage({ name })).toContain(text);
});
