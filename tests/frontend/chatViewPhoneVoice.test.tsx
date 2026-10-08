jest.mock('../../src/lib/voiceEngine', () => ({
  isSpeaking: jest.fn(() => false),
  previewVoice: jest.fn(() => Promise.resolve(false)),
  speakNatural: jest.fn((_text: string, handlers?: { onEnd?: () => void }) => { handlers?.onEnd?.(); return Promise.resolve(false); }),
  stopSpeaking: jest.fn(),
}));
import { act, fireEvent, render, screen } from '@testing-library/react';
import ChatView from '../../src/components/ChatView';
import type { Agent, Chat, User } from '../../src/types';

const mockStart = jest.fn();
const mockStop = jest.fn();
const mockCancel = jest.fn();
let mockRecordingMode = true;
let mockListening = false;
const mockHookArgs: unknown[][] = [];
jest.mock('../../src/hooks/useSpeechRecognition', () => ({
  __esModule: true,
  default: (...args: unknown[]) => (mockHookArgs.push(args), {
    supported: true,
    recordingMode: mockRecordingMode,
    listening: mockListening,
    transcribing: false,
    error: '',
    start: mockStart,
    stop: mockStop,
    cancel: mockCancel,
  }),
}));
jest.mock('../../src/lib/coachVoice', () => ({
  // The coach finishes speaking at once, handing over to the microphone.
  playCoachSpeech: jest.fn((_text: string, options: { onEnd?: () => void }) => { options.onEnd?.(); return Promise.resolve(); }),
  stopCoachAudio: jest.fn(),
}));

const agent: Agent = { id: 'communication', name: 'Communication Coach', icon: 'C', color: '#000', greeting: 'Hi', kind: 'communication' } as Agent;
const chat: Chat = { id: 'chat', agentId: 'communication', title: 'Pronunciation', messages: [{ role: 'agent', text: 'Pronounce "schedule".' }], updatedAt: 0 } as Chat;
const user: User = { id: 'u', name: 'Learner', email: 'l@example.test', mobile: '', initial: 'L' };

function renderChat(onSend = jest.fn()) {
  render(
    <ChatView
      chat={chat} agent={agent} user={user} typing={false}
      onBack={jest.fn()} onSend={onSend} onChooseOption={jest.fn()}
      attachEnabled={false} pendingFiles={[]} onAttachFiles={jest.fn()} onAttachDisabled={jest.fn()}
      transcribeAudio={jest.fn()}
    />,
  );
  return onSend;
}

beforeEach(() => {
  mockStart.mockReset();
  mockStop.mockReset();
  mockCancel.mockReset();
  mockRecordingMode = true;
  mockListening = false;
});

test('on a phone the mic stops after a 7 second pause and sends the answer by itself', () => {
  const onSend = renderChat();
  fireEvent.click(screen.getByTitle('Voice input'));
  const [onResult, options] = mockStart.mock.calls[0];
  expect(options).toMatchObject({ autoStopOnSilence: true, silenceMs: 7000 });

  act(() => { onResult('schedule', true); });
  expect(onSend).toHaveBeenCalledWith('schedule');
});

test('while recording, the student is told the answer sends itself after a 7 second pause', () => {
  mockListening = true;
  renderChat();
  expect(screen.getByRole('status')).toHaveTextContent('stop talking for 7 seconds');
  mockListening = false;
});

test('an empty transcript is not sent', () => {
  const onSend = renderChat();
  fireEvent.click(screen.getByTitle('Voice input'));
  act(() => { mockStart.mock.calls[0][0]('', true); });
  expect(onSend).not.toHaveBeenCalled();
});

test('desktop keeps the old behaviour: the text waits in the box for Send', () => {
  mockRecordingMode = false;
  const onSend = renderChat();
  fireEvent.click(screen.getByTitle('Voice input'));
  const [onResult, options] = mockStart.mock.calls[0];
  expect(options.silenceMs).toBeUndefined();
  act(() => { onResult('schedule', true); });
  expect(onSend).not.toHaveBeenCalled();
  expect(screen.getByDisplayValue('schedule')).toBeInTheDocument();
});

test('speaking practice on a phone shows the live preview but only ever sends the final text', () => {
  jest.useFakeTimers();
  const onSend = jest.fn();
  const preview = jest.fn();
  render(
    <ChatView
      chat={chat} agent={agent} user={user} typing={false}
      onBack={jest.fn()} onSend={onSend} onChooseOption={jest.fn()}
      attachEnabled={false} pendingFiles={[]} onAttachFiles={jest.fn()} onAttachDisabled={jest.fn()}
      transcribeAudio={jest.fn()} previewAudio={preview} immersiveSpeaking
    />,
  );
  expect(mockHookArgs.at(-1)?.[2]).toBe(preview);
  const [onResult, options] = mockStart.mock.calls[0];
  expect(options).toMatchObject({ autoStopOnSilence: true, silenceMs: 7000 });

  act(() => { onResult('I went for', false); });
  expect(screen.getByDisplayValue('I went for')).toBeInTheDocument();
  // The preview text stopping is not the pause: nothing is sent early.
  act(() => { jest.advanceTimersByTime(10_000); });
  expect(onSend).not.toHaveBeenCalled();

  act(() => { onResult('I went for a walk.', true); });
  expect(onSend).toHaveBeenCalledWith('I went for a walk.');
  jest.useRealTimers();
});

describe('speaking practice nudges ("are you here?")', () => {
  const coach = jest.requireMock('../../src/lib/coachVoice') as { playCoachSpeech: jest.Mock };

  function renderSpeaking() {
    const onSend = jest.fn();
    render(
      <ChatView
        chat={chat} agent={agent} user={user} typing={false}
        onBack={jest.fn()} onSend={onSend} onChooseOption={jest.fn()}
        attachEnabled={false} pendingFiles={[]} onAttachFiles={jest.fn()} onAttachDisabled={jest.fn()}
        transcribeAudio={jest.fn()} previewAudio={jest.fn()} immersiveSpeaking
      />,
    );
    return onSend;
  }

  beforeEach(() => {
    jest.useFakeTimers();
    coach.playCoachSpeech.mockClear();
  });
  afterEach(() => jest.useRealTimers());

  test('on a phone, a student who is speaking is never nudged, even before any text has appeared', () => {
    renderSpeaking();
    const [, options] = mockStart.mock.calls[0];
    act(() => { options.onVoiceDetected(); });
    act(() => { jest.advanceTimersByTime(25_000); });
    expect(coach.playCoachSpeech).toHaveBeenCalledTimes(1); // only the question itself
    expect(mockCancel).not.toHaveBeenCalled();
    expect(mockStop).not.toHaveBeenCalled();
  });

  test('on a phone, a nudge after real silence throws the silent recording away instead of sending it', () => {
    renderSpeaking();
    act(() => { jest.advanceTimersByTime(9_500); });
    expect(coach.playCoachSpeech).toHaveBeenCalledTimes(2);
    expect(coach.playCoachSpeech.mock.calls[1][0]).toContain('are you here?');
    expect(mockCancel).toHaveBeenCalledTimes(1);
    expect(mockStop).not.toHaveBeenCalled();
  });

  test('on a phone, the answer is sent after the 7 second pause without waiting for live text', () => {
    const onSend = renderSpeaking();
    const [onResult, options] = mockStart.mock.calls[0];
    expect(options).toMatchObject({ autoStopOnSilence: true, silenceMs: 7000 });
    act(() => { options.onVoiceDetected(); });
    // No preview text ever arrived; the recording ends after the pause and
    // delivers the final transcript, which is sent.
    act(() => { onResult('I cooked dinner for my family.', true); });
    expect(onSend).toHaveBeenCalledWith('I cooked dinner for my family.');
  });

  test('on a desktop the nudge still stops listening as before', () => {
    mockRecordingMode = false;
    renderSpeaking();
    act(() => { jest.advanceTimersByTime(9_500); });
    expect(coach.playCoachSpeech).toHaveBeenCalledTimes(2);
    expect(mockStop).toHaveBeenCalled();
    expect(mockCancel).not.toHaveBeenCalled();
    mockRecordingMode = true;
  });
});
