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
  private timer: ReturnType<typeof setInterval> | undefined;
  start() {
    this.state = 'recording';
    // A real recorder started with a timeslice hands over audio as it goes.
    this.timer = setInterval(() => this.ondataavailable?.({ data: new Blob(['audio so far'], { type: this.mimeType }) }), 250);
  }
  stop() {
    clearInterval(this.timer);
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

describe('auto-send after a pause (phone recording)', () => {
  let level = 0;
  class LevelAudioContext {
    state = 'running';
    resume = jest.fn(() => Promise.resolve());
    close() { this.state = 'closed'; return Promise.resolve(); }
    createMediaStreamSource() { return { connect: () => undefined }; }
    createAnalyser() {
      return {
        fftSize: 1024,
        getByteTimeDomainData(samples: Uint8Array) {
          const amplitude = Math.round(level * 128);
          samples.forEach((_, index) => { samples[index] = 128 + (index % 2 ? amplitude : -amplitude); });
        },
      };
    }
  }

  beforeEach(() => {
    jest.useFakeTimers();
    level = 0;
    Object.defineProperty(window, 'AudioContext', { configurable: true, value: LevelAudioContext });
  });

  afterEach(() => {
    jest.useRealTimers();
    delete (window as { AudioContext?: unknown }).AudioContext;
  });

  async function advance(ms: number) {
    await act(async () => { jest.advanceTimersByTime(ms); });
  }

  test('7 seconds of quiet after speaking ends the recording and delivers the text, with a countdown for the last 3', async () => {
    const transcribe = jest.fn().mockResolvedValue('I usually read before bed');
    const onResult = jest.fn();
    const countdown = jest.fn();
    const { result } = renderHook(() => useSpeechRecognition('en-US', transcribe));
    act(() => { result.current.start(onResult, { autoStopOnSilence: true, silenceMs: 7000, onSilenceCountdown: countdown }); });
    await advance(0);
    await waitFor(() => expect(FakeRecorder.latest?.state).toBe('recording'));

    level = 0.2;
    await advance(1_000);
    level = 0;
    await advance(3_500);
    expect(countdown).not.toHaveBeenCalledWith(expect.any(Number));
    await advance(1_000);
    expect(countdown).toHaveBeenCalledWith(3);
    expect(transcribe).not.toHaveBeenCalled();
    await advance(3_000);
    expect(FakeRecorder.latest?.state).toBe('inactive');
    await waitFor(() => expect(onResult).toHaveBeenCalledWith('I usually read before bed', true));
    expect(countdown).toHaveBeenLastCalledWith(null);
  });

  test('speaking again during the countdown cancels it', async () => {
    const transcribe = jest.fn().mockResolvedValue('text');
    const countdown = jest.fn();
    const { result } = renderHook(() => useSpeechRecognition('en-US', transcribe));
    act(() => { result.current.start(jest.fn(), { autoStopOnSilence: true, silenceMs: 7000, onSilenceCountdown: countdown }); });
    await advance(0);
    await waitFor(() => expect(FakeRecorder.latest?.state).toBe('recording'));
    level = 0.2;
    await advance(500);
    level = 0;
    await advance(5_200);
    expect(countdown).toHaveBeenCalledWith(2);
    level = 0.2;
    await advance(500);
    expect(countdown).toHaveBeenLastCalledWith(null);
    level = 0;
    await advance(5_000);
    expect(FakeRecorder.latest?.state).toBe('recording');
    expect(transcribe).not.toHaveBeenCalled();
  });

  test('silence before any speech never ends the recording', async () => {
    const transcribe = jest.fn();
    const { result } = renderHook(() => useSpeechRecognition('en-US', transcribe));
    act(() => { result.current.start(jest.fn(), { autoStopOnSilence: true, silenceMs: 7000 }); });
    await advance(0);
    await waitFor(() => expect(FakeRecorder.latest?.state).toBe('recording'));
    await advance(20_000);
    expect(FakeRecorder.latest?.state).toBe('recording');
    expect(transcribe).not.toHaveBeenCalled();
  });

  test('a tap resumes a meter the phone created suspended', async () => {
    let created: LevelAudioContext | null = null;
    class Suspended extends LevelAudioContext {
      state = 'suspended';
      constructor() { super(); created = this; }
    }
    Object.defineProperty(window, 'AudioContext', { configurable: true, value: Suspended });
    const { result } = renderHook(() => useSpeechRecognition('en-US', jest.fn()));
    act(() => { result.current.start(jest.fn(), { autoStopOnSilence: true }); });
    await advance(0);
    await waitFor(() => expect(created).not.toBeNull());
    const before = created!.resume.mock.calls.length;
    act(() => { document.dispatchEvent(new Event('pointerdown')); });
    expect(created!.resume.mock.calls.length).toBe(before + 1);
  });
  test('with a preview transcriber, the text appears while speaking and the final text still comes from the full recording', async () => {
    const transcribe = jest.fn().mockResolvedValue('I cooked dinner for my family.');
    const preview = jest.fn()
      .mockResolvedValueOnce('I cooked')
      .mockResolvedValue('I cooked dinner for my');
    const onResult = jest.fn();
    const { result } = renderHook(() => useSpeechRecognition('en-US', transcribe, preview));
    act(() => { result.current.start(onResult, { autoStopOnSilence: true, silenceMs: 7000 }); });
    await advance(0);
    await waitFor(() => expect(FakeRecorder.latest?.state).toBe('recording'));

    // No preview before the student says anything (the meter works here).
    await advance(2_000);
    expect(preview).not.toHaveBeenCalled();

    level = 0.2;
    await advance(1_000);
    await waitFor(() => expect(onResult).toHaveBeenCalledWith('I cooked', false));
    await advance(3_000);
    await waitFor(() => expect(onResult).toHaveBeenCalledWith('I cooked dinner for my', false));
    expect(preview.mock.calls[0][0]).toBeInstanceOf(Blob);
    expect(transcribe).not.toHaveBeenCalled();

    level = 0;
    await advance(7_500);
    await waitFor(() => expect(onResult).toHaveBeenCalledWith('I cooked dinner for my family.', true));
    expect(transcribe).toHaveBeenCalledTimes(1);
  });

  test('when the phone keeps the meter suspended, previews still run and new words count as speech for the pause', async () => {
    class Suspended extends LevelAudioContext { state = 'suspended'; }
    Object.defineProperty(window, 'AudioContext', { configurable: true, value: Suspended });
    const transcribe = jest.fn().mockResolvedValue('I went for a walk.');
    const preview = jest.fn()
      .mockResolvedValueOnce('I went')
      .mockResolvedValue('I went for a walk');
    const onResult = jest.fn();
    const { result } = renderHook(() => useSpeechRecognition('en-US', transcribe, preview));
    act(() => { result.current.start(onResult, { autoStopOnSilence: true, silenceMs: 7000 }); });
    await advance(0);
    await waitFor(() => expect(FakeRecorder.latest?.state).toBe('recording'));

    await advance(1_000);
    await waitFor(() => expect(onResult).toHaveBeenCalledWith('I went', false));
    await advance(3_000);
    await waitFor(() => expect(onResult).toHaveBeenCalledWith('I went for a walk', false));
    // The text stops changing: 7s later the recording ends and is sent.
    expect(transcribe).not.toHaveBeenCalled();
    await advance(7_500);
    await waitFor(() => expect(onResult).toHaveBeenCalledWith('I went for a walk.', true));
  });

  test('a failed preview is ignored and the final transcription still happens', async () => {
    const transcribe = jest.fn().mockResolvedValue('Final answer.');
    const preview = jest.fn().mockRejectedValue(new Error('offline'));
    const onResult = jest.fn();
    const { result } = renderHook(() => useSpeechRecognition('en-US', transcribe, preview));
    act(() => { result.current.start(onResult, { autoStopOnSilence: true, silenceMs: 7000 }); });
    await advance(0);
    await waitFor(() => expect(FakeRecorder.latest?.state).toBe('recording'));
    level = 0.2;
    await advance(4_000);
    expect(preview).toHaveBeenCalled();
    act(() => { result.current.stop(); });
    await waitFor(() => expect(onResult).toHaveBeenCalledWith('Final answer.', true));
    expect(result.current.error).toBe('');
  });
});
