import { speakBrowserText, unlockSpeechSynthesis } from '../../src/lib/browserSpeech';

class FakeUtterance {
  text: string;
  volume = 1;
  lang = '';
  rate = 1;
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(text: string) {
    this.text = text;
  }
}

describe('browser speech helpers', () => {
  const synthesis = {
    getVoices: jest.fn(() => [{}]),
    resume: jest.fn(),
    cancel: jest.fn(),
    speak: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: synthesis });
    Object.defineProperty(globalThis, 'SpeechSynthesisUtterance', { configurable: true, value: FakeUtterance });
  });

  test('unlocks speech from the user gesture with a silent utterance', () => {
    expect(unlockSpeechSynthesis()).toBe(true);
    expect(synthesis.resume).toHaveBeenCalled();
    expect(synthesis.speak).toHaveBeenCalledWith(expect.objectContaining({ volume: 0 }));
  });

  test('waits for the browser engine and reports a successful question read', async () => {
    synthesis.speak.mockImplementation((utterance: FakeUtterance) => {
      utterance.onstart?.();
      utterance.onend?.();
    });
    const onEnd = jest.fn();
    await expect(speakBrowserText('What is a list?', { onEnd })).resolves.toBe(true);
    expect(synthesis.resume).toHaveBeenCalled();
    expect(synthesis.cancel).toHaveBeenCalled();
    expect(synthesis.speak).toHaveBeenCalledWith(expect.objectContaining({ text: 'What is a list?' }));
    expect(onEnd).toHaveBeenCalledTimes(1);
  });
});
