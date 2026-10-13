const mockSpeak = jest.fn();
const mockStopSpeaking = jest.fn();
jest.mock('../../src/lib/voiceEngine', () => ({
  speakNatural: (...args: unknown[]) => mockSpeak(...args),
  stopSpeaking: () => mockStopSpeaking(),
}));
jest.mock('../../src/lib/orchestratorApi', () => ({ transcribeGeneralAudio: jest.fn() }));
jest.mock('../../src/components/Logo', () => ({ Logo: () => <span>DD</span> }));
const mockStart = jest.fn();
const mockStop = jest.fn();
const mockCancel = jest.fn();
let mockListening = false;
jest.mock('../../src/hooks/useSpeechRecognition', () => ({
  __esModule: true,
  default: () => ({ supported: true, listening: mockListening, transcribing: false, error: '', start: mockStart, stop: mockStop, cancel: mockCancel }),
}));
import { act, fireEvent, render, screen } from '@testing-library/react';
import VoiceConversation, { CONVERSATION_PAUSE_MS } from '../../src/components/VoiceConversation';
import type { ChatMessage } from '../../src/types';

const msg = (role: 'user' | 'agent', text: string): ChatMessage => ({ role, text, time: '' });

beforeEach(() => {
  mockSpeak.mockReset();
  mockStart.mockReset();
  mockStop.mockReset();
  mockCancel.mockReset();
  mockStopSpeaking.mockReset();
  mockListening = false;
  mockStart.mockReturnValue(true);
});

test('listens, sends after a 5 second pause, speaks the reply, then listens again', () => {
  let speakDone: () => void = () => {};
  mockSpeak.mockImplementation((_text: string, handlers: { onEnd: () => void }) => { speakDone = handlers.onEnd; return Promise.resolve(true); });
  const onSend = jest.fn();
  const messages = [msg('agent', 'Hi!')];
  const { rerender } = render(<VoiceConversation messages={messages} typing={false} onSend={onSend} onClose={jest.fn()} />);
  expect(mockStart).toHaveBeenCalledTimes(1);
  expect(mockStart.mock.calls[0][1]).toEqual(expect.objectContaining({ autoStopOnSilence: true, silenceMs: CONVERSATION_PAUSE_MS }));
  expect(CONVERSATION_PAUSE_MS).toBe(5000);

  act(() => { mockStart.mock.calls[0][0]('What is DigiDARA', false); });
  expect(screen.getByText('“What is DigiDARA”')).toBeInTheDocument();
  act(() => { mockStart.mock.calls[0][0]('What is DigiDARA?', true); });
  expect(onSend).toHaveBeenCalledWith('What is DigiDARA?');
  expect(screen.getByText('Thinking...')).toBeInTheDocument();

  rerender(<VoiceConversation messages={[...messages, msg('user', 'What is DigiDARA?')]} typing onSend={onSend} onClose={jest.fn()} />);
  expect(mockSpeak).not.toHaveBeenCalled();
  rerender(<VoiceConversation messages={[...messages, msg('user', 'What is DigiDARA?'), msg('agent', 'Your AI career coach!')]} typing={false} onSend={onSend} onClose={jest.fn()} />);
  expect(mockSpeak).toHaveBeenCalledWith('Your AI career coach!', expect.anything(), true);
  expect(mockStart).toHaveBeenCalledTimes(1);
  act(() => { speakDone(); });
  expect(mockStart).toHaveBeenCalledTimes(2);
});

test('opened right after a question was sent, it waits for that reply and speaks it', () => {
  mockSpeak.mockReturnValue(Promise.resolve(true));
  const sent = [msg('user', 'Hello')];
  const { rerender } = render(<VoiceConversation messages={sent} typing awaitingReply onSend={jest.fn()} onClose={jest.fn()} />);
  expect(mockStart).not.toHaveBeenCalled();
  rerender(<VoiceConversation messages={[...sent, msg('agent', 'Hi there!')]} typing={false} awaitingReply onSend={jest.fn()} onClose={jest.fn()} />);
  expect(mockSpeak).toHaveBeenCalledWith('Hi there!', expect.anything(), true);
});

test('tapping the logo while it speaks interrupts it and listens; ending stops everything', () => {
  mockSpeak.mockReturnValue(Promise.resolve(true));
  const onClose = jest.fn();
  const sent = [msg('user', 'Hello')];
  const { rerender } = render(<VoiceConversation messages={sent} typing awaitingReply onSend={jest.fn()} onClose={onClose} />);
  rerender(<VoiceConversation messages={[...sent, msg('agent', 'Hi there!')]} typing={false} awaitingReply onSend={jest.fn()} onClose={onClose} />);
  fireEvent.click(screen.getByRole('button', { name: 'Interrupt' }));
  expect(mockStopSpeaking).toHaveBeenCalled();
  expect(mockStart).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'End voice chat' }));
  expect(mockCancel).toHaveBeenCalled();
  expect(onClose).toHaveBeenCalled();
});
