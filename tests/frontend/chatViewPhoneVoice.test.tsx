import { act, fireEvent, render, screen } from '@testing-library/react';
import ChatView from '../../src/components/ChatView';
import type { Agent, Chat, User } from '../../src/types';

const mockStart = jest.fn();
const mockStop = jest.fn();
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
