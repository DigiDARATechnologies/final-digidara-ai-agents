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
jest.mock('../../src/lib/orchestratorApi', () => ({ transcribeGeneralAudio: jest.fn(), warmBoss: jest.fn() }));
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

test('Boss greets, then listens; a 1.5 second pause (or the live transcript) sends the question', () => {
  let greetingDone: () => void = () => {};
  mockSpeak.mockImplementation((_text: string, handlers: { onEnd: () => void }) => { greetingDone = handlers.onEnd; return Promise.resolve(true); });
  const onSend = jest.fn();
  const { unmount } = render(<VoiceConversation messages={[msg('agent', 'Hi!')]} typing={false} learnerName="Senthil Kumar" onSend={onSend} onClose={jest.fn()} />);
  expect(isVoiceConversationOpen()).toBe(true);
  expect(mockSpeak).toHaveBeenCalledWith(bossGreeting('Senthil Kumar'), expect.anything(), true);
  expect(bossGreeting('Senthil Kumar')).toBe("Hi Senthil, I'm Boss. What can I help you with?");
  expect(mockStart).not.toHaveBeenCalled();
  act(() => { greetingDone(); });
  expect(mockStart).toHaveBeenCalledTimes(1);
  expect(mockStart.mock.calls[0][1]).toEqual(expect.objectContaining({ autoStopOnSilence: true, silenceMs: CONVERSATION_PAUSE_MS, finalFromPreview: true }));
  expect(CONVERSATION_PAUSE_MS).toBe(1500);
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

test('"just a minute" keeps Boss listening, and the whole question is sent together', () => {
  jest.useFakeTimers();
  mockSpeak.mockImplementation((_text: string, handlers: { onEnd: () => void }) => { handlers.onEnd(); return Promise.resolve(true); });
  const onSend = jest.fn();
  render(<VoiceConversation messages={[]} typing={false} onSend={onSend} onClose={jest.fn()} />);
  act(() => { mockStart.mock.calls[0][0]('Tell me about the Capstone agent, just a minute', true); });
  expect(onSend).not.toHaveBeenCalled();
  act(() => { jest.advanceTimersByTime(150); });
  expect(mockStart).toHaveBeenCalledTimes(2);
  act(() => { mockStart.mock.calls[1][0]('and how long the project takes.', true); });
  expect(onSend).toHaveBeenCalledWith('Tell me about the Capstone agent and how long the project takes.');
  jest.useRealTimers();
});

test('the next question is sent with the newest onSend, not the one from when the reply began', () => {
  // The reply's speech queue is made when its first word streams in; the
  // question asked after it must not be sent with that render's onSend
  // (its copy of the chat still held the reply's first word only).
  const early = jest.fn();
  const latest = jest.fn();
  const asked = [msg('agent', 'Hi!'), msg('user', 'introduce yourself')];
  const { rerender } = render(<VoiceConversation messages={asked} typing awaitingReply onSend={early} onClose={jest.fn()} />);
  rerender(<VoiceConversation messages={[...asked, msg('agent', 'Hell', true)]} typing={false} awaitingReply onSend={early} onClose={jest.fn()} />);
  const done = [...asked, msg('agent', 'Hello everyone! I am Boss.')];
  rerender(<VoiceConversation messages={done} typing={false} awaitingReply onSend={latest} onClose={jest.fn()} />);
  act(() => { mockQueues[0].onEnd?.(); });
  const onHeard = mockStart.mock.calls.at(-1)![0] as (text: string, final: boolean) => void;
  act(() => { onHeard('suggest me jobs', true); });
  expect(latest).toHaveBeenCalledWith('suggest me jobs');
  expect(early).not.toHaveBeenCalled();
});

test('opened by "Hey Boss, ..." it asks that straight away; the wake words are never part of a question', () => {
  const onSend = jest.fn();
  render(<VoiceConversation messages={[msg('agent', 'Hi!')]} typing={false} firstQuestion="are you there?" onSend={onSend} onClose={jest.fn()} />);
  expect(mockSpeak).not.toHaveBeenCalled();
  expect(onSend).toHaveBeenCalledWith('are you there?');
  expect(screen.getByText('Thinking...')).toBeInTheDocument();
});

test('"Hey Boss, what is a resume" is sent as "what is a resume"', () => {
  let greetingDone: () => void = () => {};
  mockSpeak.mockImplementation((_text: string, handlers: { onEnd: () => void }) => { greetingDone = handlers.onEnd; return Promise.resolve(true); });
  const onSend = jest.fn();
  render(<VoiceConversation messages={[msg('agent', 'Hi!')]} typing={false} onSend={onSend} onClose={jest.fn()} />);
  act(() => { greetingDone(); });
  act(() => { mockStart.mock.calls[0][0]('Hey Boss, what is a resume', true); });
  expect(onSend).toHaveBeenCalledWith('what is a resume');
});

test('in the Boss chat voice conversation, "close the tab" ends it and "open aptitude" goes there and hands over to the Boss panel', async () => {
  const { continueInBossPanel, setBossPanelOpener } = await import('../../src/lib/voiceReply');
  expect(typeof continueInBossPanel).toBe('function');
  const panel = jest.fn();
  const unregister = setBossPanelOpener(panel);
  jest.useFakeTimers();
  try {
    const onSend = jest.fn();
    const onClose = jest.fn();
    const onNavigate = jest.fn();
    let spoken: { onEnd: () => void } = { onEnd: () => {} };
    mockSpeak.mockImplementation((_text: string, handlers: { onEnd: () => void }) => { spoken = handlers; return Promise.resolve(true); });
    const first = render(<VoiceConversation messages={[]} typing={false} onSend={onSend} onClose={onClose} onNavigate={onNavigate} />);
    act(() => { spoken.onEnd(); });
    act(() => { mockStart.mock.calls[0][0]('open the aptitude agent', true); });
    expect(onSend).not.toHaveBeenCalled();
    expect(mockSpeak).toHaveBeenLastCalledWith('Opening Aptitude Trainer.', expect.anything(), true);
    act(() => { spoken.onEnd(); });
    expect(onNavigate).toHaveBeenCalledWith('aptitude');
    act(() => { jest.advanceTimersByTime(300); });
    expect(panel).toHaveBeenCalledTimes(1);
    first.unmount();

    mockStart.mockClear();
    render(<VoiceConversation messages={[]} typing={false} onSend={onSend} onClose={onClose} onNavigate={onNavigate} />);
    act(() => { spoken.onEnd(); });
    act(() => { mockStart.mock.calls[0][0]('Hey Boss close the tab', true); });
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onSend).not.toHaveBeenCalled();
  } finally {
    jest.useRealTimers();
    unregister();
  }
});
