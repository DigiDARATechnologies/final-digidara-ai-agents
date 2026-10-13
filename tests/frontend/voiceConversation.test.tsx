const mockSpeak = jest.fn();
const mockStopSpeaking = jest.fn();
type MockQueue = { pushed: string[]; ended: boolean; onEnd?: () => void };
const mockQueues: MockQueue[] = [];
jest.mock('../../src/lib/voiceEngine', () => ({
  speakNatural: (...args: unknown[]) => mockSpeak(...args),
  stopSpeaking: () => mockStopSpeaking(),
  createSpeechQueue: (handlers: { onEnd?: () => void }) => {
    const queue: MockQueue = { pushed: [], ended: false, onEnd: handlers.onEnd };
    mockQueues.push(queue);
    return {
      started: Promise.resolve(true),
      push: (text: string) => { queue.pushed.push(text); },
      end: () => { queue.ended = true; },
    };
  },
}));
jest.mock('../../src/lib/orchestratorApi', () => ({ transcribeGeneralAudio: jest.fn() }));
const mockWatchers: Array<() => void> = [];
const mockUnwatch = jest.fn();
jest.mock('../../src/lib/voiceActivity', () => ({
  watchForSpeech: (onSpeech: () => void) => { mockWatchers.push(onSpeech); return mockUnwatch; },
}));
jest.mock('../../src/components/Logo', () => ({ Logo: () => <span>DD</span> }));
const mockStart = jest.fn();
const mockStop = jest.fn();
const mockCancel = jest.fn();
jest.mock('../../src/hooks/useSpeechRecognition', () => ({
  __esModule: true,
  default: () => ({ supported: true, listening: false, transcribing: false, error: '', start: mockStart, stop: mockStop, cancel: mockCancel }),
}));
import { act, fireEvent, render, screen } from '@testing-library/react';
import VoiceConversation, { bossGreeting, CONVERSATION_PAUSE_MS } from '../../src/components/VoiceConversation';
import { isVoiceConversationOpen } from '../../src/lib/voiceReply';
import type { ChatMessage } from '../../src/types';

const msg = (role: 'user' | 'agent', text: string, streaming?: boolean): ChatMessage => ({ role, text, time: '', streaming });

beforeEach(() => {
  mockSpeak.mockReset();
  mockStart.mockReset();
  mockStop.mockReset();
  mockCancel.mockReset();
  mockStopSpeaking.mockReset();
  mockQueues.length = 0;
  mockWatchers.length = 0;
  mockUnwatch.mockReset();
  mockStart.mockReturnValue(true);
});

test('Boss greets, then listens; a 5 second pause (or the live transcript) sends the question', () => {
  let greetingDone: () => void = () => {};
  mockSpeak.mockImplementation((_text: string, handlers: { onEnd: () => void }) => { greetingDone = handlers.onEnd; return Promise.resolve(true); });
  const onSend = jest.fn();
  const { unmount } = render(<VoiceConversation messages={[msg('agent', 'Hi!')]} typing={false} learnerName="Senthil Kumar" onSend={onSend} onClose={jest.fn()} />);
  expect(isVoiceConversationOpen()).toBe(true);
  expect(mockSpeak).toHaveBeenCalledWith(bossGreeting('Senthil Kumar'), expect.anything(), true);
  expect(bossGreeting('Senthil Kumar')).toBe("Hi Senthil! I'm Boss, your DigiDARA AI assistant. Ask me anything about DigiDARA and its agents.");
  expect(mockStart).not.toHaveBeenCalled();
  act(() => { greetingDone(); });
  expect(mockStart).toHaveBeenCalledTimes(1);
  expect(mockStart.mock.calls[0][1]).toEqual(expect.objectContaining({ autoStopOnSilence: true, silenceMs: CONVERSATION_PAUSE_MS, finalFromPreview: true }));
  expect(CONVERSATION_PAUSE_MS).toBe(5000);
  act(() => { mockStart.mock.calls[0][0]('What is DigiDARA', false); });
  // No words on screen, only the logo.
  expect(screen.queryByText(/What is DigiDARA/)).not.toBeInTheDocument();
  act(() => { mockStart.mock.calls[0][0]('What is DigiDARA?', true); });
  expect(onSend).toHaveBeenCalledWith('What is DigiDARA?');
  expect(screen.getByText('Thinking...')).toHaveClass('visually-hidden');
  unmount();
  expect(isVoiceConversationOpen()).toBe(false);
});

test('a streaming reply is spoken sentence by sentence while it is written, then it listens again', () => {
  const sent = [msg('user', 'Hello')];
  const view = (messages: ChatMessage[], typing: boolean) =>
    <VoiceConversation messages={messages} typing={typing} awaitingReply onSend={jest.fn()} onClose={jest.fn()} />;
  const { rerender } = render(view(sent, true));
  expect(mockStart).not.toHaveBeenCalled();
  rerender(view([...sent, msg('agent', 'Hi there! I am Bo', true)], false));
  expect(mockQueues).toHaveLength(1);
  expect(mockQueues[0].pushed).toEqual(['Hi there!']);
  rerender(view([...sent, msg('agent', 'Hi there! I am Boss. Ask me', true)], false));
  expect(mockQueues[0].pushed).toEqual(['Hi there!', ' I am Boss.']);
  rerender(view([...sent, msg('agent', 'Hi there! I am Boss. Ask me anything', false)], false));
  expect(mockQueues[0].pushed).toEqual(['Hi there!', ' I am Boss.', ' Ask me anything']);
  expect(mockQueues[0].ended).toBe(true);
  act(() => { mockQueues[0].onEnd?.(); });
  expect(mockStart).toHaveBeenCalledTimes(1);
});

test('a whole reply (no streaming) is spoken at once', () => {
  const sent = [msg('user', 'Hello')];
  const { rerender } = render(<VoiceConversation messages={sent} typing awaitingReply onSend={jest.fn()} onClose={jest.fn()} />);
  rerender(<VoiceConversation messages={[...sent, msg('agent', 'Hi there!')]} typing={false} awaitingReply onSend={jest.fn()} onClose={jest.fn()} />);
  expect(mockQueues[0]).toMatchObject({ pushed: ['Hi there!'], ended: true });
});

test('tapping the logo while it speaks interrupts it and listens once; ending stops everything', () => {
  const onClose = jest.fn();
  const sent = [msg('user', 'Hello')];
  const { rerender } = render(<VoiceConversation messages={sent} typing awaitingReply onSend={jest.fn()} onClose={onClose} />);
  rerender(<VoiceConversation messages={[...sent, msg('agent', 'Hi there!')]} typing={false} awaitingReply onSend={jest.fn()} onClose={onClose} />);
  fireEvent.click(screen.getByRole('button', { name: 'Interrupt' }));
  expect(mockStopSpeaking).toHaveBeenCalled();
  expect(mockStart).toHaveBeenCalledTimes(1);
  // The interrupted reply ending afterwards does not start a second listen.
  act(() => { mockQueues[0].onEnd?.(); });
  expect(mockStart).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'End voice chat' }));
  expect(mockCancel).toHaveBeenCalled();
  expect(onClose).toHaveBeenCalled();
});

test('talking over Boss interrupts it: it stops speaking and listens', () => {
  const sent = [msg('user', 'Hello')];
  const { rerender } = render(<VoiceConversation messages={sent} typing awaitingReply onSend={jest.fn()} onClose={jest.fn()} />);
  expect(mockWatchers).toHaveLength(0); // not listening for interruptions while thinking
  rerender(<VoiceConversation messages={[...sent, msg('agent', 'Hi there! Long answer.')]} typing={false} awaitingReply onSend={jest.fn()} onClose={jest.fn()} />);
  expect(mockWatchers).toHaveLength(1);
  act(() => { mockWatchers[0](); });
  expect(mockStopSpeaking).toHaveBeenCalled();
  expect(mockStart).toHaveBeenCalledTimes(1);
  expect(mockUnwatch).toHaveBeenCalled(); // the watch ends once it is listening
  // The interrupted reply finishing later does not start a second listen.
  act(() => { mockQueues[0].onEnd?.(); });
  expect(mockStart).toHaveBeenCalledTimes(1);
});
