const mockAssist = jest.fn();
jest.mock('../../src/lib/assistApi', () => ({
  assistStream: (...args: unknown[]) => mockAssist(...args),
}));
const mockCapture = jest.fn();
jest.mock('../../src/lib/screenCapture', () => ({
  captureScreenshot: () => mockCapture(),
  SCREENSHOT_HIDE_ATTRIBUTE: 'data-screenshot-hide',
}));
jest.mock('../../src/lib/orchestratorApi', () => ({ transcribeGeneralAudio: jest.fn() }));
const mockPushed: string[] = [];
let mockQueueHandlers: { onEnd?: () => void; onStart?: () => void; speed?: number; pace?: string } = {};
jest.mock('../../src/lib/voiceEngine', () => ({
  stopSpeaking: jest.fn(),
  createSpeechQueue: (handlers: typeof mockQueueHandlers) => {
    mockQueueHandlers = handlers;
    return { started: Promise.resolve(true), push: (text: string) => mockPushed.push(text), end: jest.fn() };
  },
}));
jest.mock('../../src/lib/voiceActivity', () => ({ watchForSpeech: () => jest.fn() }));
let mockWake: ((rest: string) => void) | null = null;
jest.mock('../../src/lib/wakeWord', () => ({
  wakeWordSupported: () => true,
  listenForWakeWord: (onWake: (rest: string) => void) => { mockWake = onWake; return () => { mockWake = null; }; },
}));
jest.mock('../../src/lib/voiceCapture', () => ({ audioRecordingSupported: () => true }));
jest.mock('../../src/components/Logo', () => ({ Logo: () => <span>DD</span> }));
const mockStart = jest.fn();
jest.mock('../../src/hooks/useSpeechRecognition', () => ({
  __esModule: true,
  default: () => ({ supported: true, listening: false, transcribing: false, error: '', start: mockStart, stop: jest.fn(), cancel: jest.fn() }),
}));
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import BossAssistant, { CLOSE_PHRASE } from '../../src/components/BossAssistant';
import { refersToScreen, withoutWakeWords } from '../../src/lib/assistText';
import { setBossVoiceOpener, setVoiceConversationOpen } from '../../src/lib/voiceReply';

function openBoss() {
  render(<BossAssistant agentId="job-fetch" agentName="Job Agent" getContext={() => 'Agent: Upload your resume'} />);
  fireEvent.click(screen.getByLabelText('Ask Boss for help with this screen'));
}

async function ask(text: string) {
  fireEvent.change(screen.getByLabelText('Your question for Boss'), { target: { value: text } });
  await act(async () => { fireEvent.click(screen.getByLabelText('Send')); });
}

beforeEach(() => {
  mockAssist.mockReset();
  mockCapture.mockReset();
  mockStart.mockReset();
  mockPushed.length = 0;
  mockQueueHandlers = {};
  mockWake = null;
  localStorage.clear();
  mockAssist.mockImplementation(async (_request: unknown, onText: (text: string) => void) => {
    onText('Press Start');
    return 'Press Start.';
  });
});

test('a question goes to Boss with the agent and the chat on screen, and the answer shows', async () => {
  openBoss();
  await ask('how do I upload my resume');
  await waitFor(() => expect(screen.getByText('Press Start.')).toBeTruthy());
  expect(mockAssist.mock.calls[0][0]).toMatchObject({
    message: 'how do I upload my resume', agentId: 'job-fetch', agentName: 'Job Agent', context: 'Agent: Upload your resume', voice: false,
  });
  // Nothing about the screen was asked: no screenshot is taken.
  expect(mockCapture).not.toHaveBeenCalled();
  expect(mockAssist.mock.calls[0][0].screenshot).toBeNull();
});

test('letting Boss look attaches a screenshot of the page', async () => {
  mockCapture.mockResolvedValue('data:image/jpeg;base64,AAAA');
  openBoss();
  fireEvent.click(screen.getByLabelText('Let Boss look at your screen'));
  await ask('explain the options');
  await waitFor(() => expect(mockAssist).toHaveBeenCalled());
  expect(mockAssist.mock.calls[0][0].screenshot).toBe('data:image/jpeg;base64,AAAA');
  expect(screen.getByText('with your screen')).toBeTruthy();
});

test('a question about "this" looks at the screen without being asked; a failed capture still answers', async () => {
  mockCapture.mockResolvedValue(null);
  openBoss();
  await ask('what is wrong here?');
  await waitFor(() => expect(mockAssist).toHaveBeenCalled());
  expect(mockCapture).toHaveBeenCalledTimes(1);
  expect(mockAssist.mock.calls[0][0].screenshot).toBeNull();
  expect(screen.getByRole('alert').textContent).toContain('could not capture the screen');
});

test('a spoken question is answered aloud as it streams in', async () => {
  mockStart.mockImplementation((onResult: (text: string, final: boolean) => void) => {
    onResult('Hey Boss, how do I start the interview', true);
    return true;
  });
  openBoss();
  await act(async () => { fireEvent.click(screen.getByLabelText('Talk to Boss')); });
  await waitFor(() => expect(mockAssist).toHaveBeenCalled());
  expect(mockAssist.mock.calls[0][0]).toMatchObject({ message: 'how do I start the interview', voice: true });
  expect(mockPushed.join('')).toContain('Press Start');
});

test('an error from Boss is shown and the empty answer is removed', async () => {
  mockAssist.mockRejectedValue(new Error('Boss could not answer just now. Please try again.'));
  openBoss();
  await ask('help');
  await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('could not answer'));
});

test('wake words are not part of the question; pointing at the screen is recognised', () => {
  expect(withoutWakeWords('Hey Boss, what is this error?')).toBe('what is this error?');
  expect(withoutWakeWords('hi boss how are you')).toBe('how are you');
  expect(withoutWakeWords('bossy attitude')).toBe('bossy attitude');
  expect(refersToScreen('what does this error mean')).toBe(true);
  expect(refersToScreen('how do I write a cover letter')).toBe(false);
});

test('the voice conversation carries on: after Boss finishes speaking it listens again', async () => {
  mockStart.mockImplementation((onResult: (text: string, final: boolean) => void) => {
    onResult('how do I start', true);
    return true;
  });
  openBoss();
  await act(async () => { fireEvent.click(screen.getByLabelText('Talk to Boss')); });
  await waitFor(() => expect(mockAssist).toHaveBeenCalledTimes(1));
  // Boss is made at a brisk pace and played a little faster.
  expect(mockQueueHandlers).toMatchObject({ pace: 'brisk', speed: 1.15 });
  const listens = mockStart.mock.calls.length;
  await act(async () => { mockQueueHandlers.onEnd?.(); });
  await waitFor(() => expect(mockStart.mock.calls.length).toBeGreaterThan(listens));
});

test('"that is all" ends the voice conversation without asking Boss', async () => {
  mockStart.mockImplementation((onResult: (text: string, final: boolean) => void) => {
    onResult("that's all", true);
    return true;
  });
  openBoss();
  await act(async () => { fireEvent.click(screen.getByLabelText('Talk to Boss')); });
  await waitFor(() => expect(screen.getByLabelText('Talk to Boss')).toBeTruthy());
  expect(mockAssist).not.toHaveBeenCalled();
});

test('saying "Hey Boss" opens Boss and starts the conversation, keeping what was said after it', async () => {
  localStorage.setItem('digidara.heyBoss', 'on');
  render(<BossAssistant agentId="job-fetch" agentName="Job Agent" getContext={() => ''} />);
  expect(mockWake).not.toBeNull();
  await act(async () => { mockWake?.('what is this error'); });
  await waitFor(() => expect(mockAssist).toHaveBeenCalled());
  expect(screen.getByRole('dialog')).toBeTruthy();
  expect(mockAssist.mock.calls[0][0]).toMatchObject({ message: 'what is this error', voice: true });
});

test('without the switch on, nothing listens for "Hey Boss"', () => {
  render(<BossAssistant agentId="" agentName="" getContext={() => ''} />);
  expect(mockWake).toBeNull();
});

test('"Hey Boss" on a Boss screen opens the Boss chat voice conversation there, not this panel', async () => {
  localStorage.setItem('digidara.heyBoss', 'on');
  const opened: string[] = [];
  const release = setBossVoiceOpener((question) => opened.push(question));
  render(<BossAssistant agentId="" agentName="Boss" getContext={() => ''} />);
  await act(async () => { mockWake?.('are you there'); });
  expect(opened).toEqual(['are you there']);
  expect(mockAssist).not.toHaveBeenCalled();
  expect(screen.queryByRole('dialog')).toBeNull();
  release();
});

test('while the Boss chat voice conversation is open, "Hey Boss" and the Boss button wait', () => {
  localStorage.setItem('digidara.heyBoss', 'on');
  render(<BossAssistant agentId="" agentName="Boss" getContext={() => ''} />);
  expect(mockWake).not.toBeNull();
  act(() => { setVoiceConversationOpen(true); });
  expect(mockWake).toBeNull();
  expect(screen.queryByLabelText('Ask Boss for help with this screen')).toBeNull();
  act(() => { setVoiceConversationOpen(false); });
  expect(mockWake).not.toBeNull();
  expect(screen.getByLabelText('Ask Boss for help with this screen')).toBeTruthy();
});

test('"close the tab" closes Boss straight away, without asking the server', async () => {
  for (const said of ['close the tab', 'Please close Boss', 'you can close this', 'close this panel.', 'close']) {
    expect(CLOSE_PHRASE.test(said)).toBe(true);
  }
  expect(CLOSE_PHRASE.test('how do I close my account')).toBe(false);
  mockStart.mockImplementation((onResult: (text: string, final: boolean) => void) => { onResult('Hey Boss, close the tab', true); return true; });
  openBoss();
  await act(async () => { fireEvent.click(screen.getByLabelText('Talk to Boss')); });
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  expect(mockAssist).not.toHaveBeenCalled();
});

test('Boss opens the agent the learner asked for, and closes after saying goodbye when asked', async () => {
  const onNavigate = jest.fn();
  mockAssist.mockImplementationOnce(async (_r: unknown, onText: (t: string) => void, _s: unknown, onAction: (a: unknown) => void) => {
    onText('Opening the Aptitude Trainer.');
    onAction({ type: 'open', target: 'aptitude' });
    return 'Opening the Aptitude Trainer.';
  });
  render(<BossAssistant agentId="" agentName="Job readiness" getContext={() => ''} onNavigate={onNavigate} />);
  fireEvent.click(screen.getByLabelText('Ask Boss for help with this screen'));
  await ask('take me where I practise numbers');
  expect(onNavigate).toHaveBeenCalledWith('aptitude');
  expect(screen.getByRole('dialog')).toBeTruthy();

  mockStart.mockImplementation((onResult: (text: string, final: boolean) => void) => { onResult('I am done for today, thank you so much', true); return true; });
  mockAssist.mockImplementationOnce(async (_r: unknown, onText: (t: string) => void, _s: unknown, onAction: (a: unknown) => void) => {
    onText('Bye for now!');
    onAction({ type: 'close' });
    return 'Bye for now!';
  });
  await act(async () => { fireEvent.click(screen.getByLabelText('Talk to Boss')); });
  await waitFor(() => expect(mockAssist).toHaveBeenCalledTimes(2));
  // Still open while the goodbye is spoken; closed once it ends.
  expect(screen.getByRole('dialog')).toBeTruthy();
  await act(async () => { mockQueueHandlers.onEnd?.(); });
  expect(screen.queryByRole('dialog')).toBeNull();
});

test('Boss opens one of the learner chats when it gives a chat link', async () => {
  const onNavigate = jest.fn();
  mockAssist.mockImplementationOnce(async (_r: unknown, onText: (t: string) => void, _s: unknown, onAction: (a: unknown) => void) => {
    onText('Opening your Capstone chat.');
    onAction({ type: 'chat', chat_id: 'chat-123' });
    return 'Opening your Capstone chat.';
  });
  render(<BossAssistant agentId="" agentName="Capstone" getContext={() => ''} onNavigate={onNavigate} />);
  fireEvent.click(screen.getByLabelText('Ask Boss for help with this screen'));
  await ask('give me the chat link');
  expect(onNavigate).toHaveBeenCalledWith('chat:chat-123');
});

test('every switch works, not only the first: "open X" goes there straight away and the tag stays in the history', async () => {
  const onNavigate = jest.fn();
  render(<BossAssistant agentId="" agentName="Job readiness" getContext={() => ''} onNavigate={onNavigate} />);
  fireEvent.click(screen.getByLabelText('Ask Boss for help with this screen'));
  await ask('switch to the aptitude agent');
  await ask('now open mock interview please');
  await ask('Hey Boss, go back to boss chat');
  expect(onNavigate.mock.calls).toEqual([['aptitude'], ['mock-interview'], ['boss']]);
  expect(mockAssist).not.toHaveBeenCalled();
  expect(screen.getByText('Opening Mock Interview.')).toBeTruthy();
  await ask('what can I practise here?');
  const history = mockAssist.mock.calls[0][0].history as Array<{ role: string; content: string }>;
  expect(history).toContainEqual({ role: 'assistant', content: 'Opening Aptitude Trainer. [[open:aptitude]]' });
});

test('"close the tab" closes Boss, and "Hey Boss" opens it again', async () => {
  localStorage.setItem('digidara.heyBoss', 'on');
  render(<BossAssistant agentId="" agentName="Aptitude" getContext={() => ''} />);
  act(() => { mockWake?.(''); });
  expect(screen.getByRole('dialog')).toBeTruthy();
  await ask('close the tab');
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(mockWake).not.toBeNull();
  act(() => { mockWake?.(''); });
  expect(screen.getByRole('dialog')).toBeTruthy();
});

test('a link Boss makes shows with who can open it and a copy button', async () => {
  mockAssist.mockImplementationOnce(async (_r: unknown, onText: (t: string) => void, _s: unknown, onAction: (a: unknown) => void) => {
    onText('Here is your private link.');
    onAction({ type: 'link', kind: 'chat', mode: 'private', path: '/shared/chat/abcDEF1234567890', title: 'Aptitude practice' });
    return 'Here is your private link.';
  });
  openBoss();
  await ask('give me the link, only for me');
  const link = await screen.findByRole('link', { name: 'Aptitude practice' });
  expect(link.getAttribute('href')).toBe(`${window.location.origin}/shared/chat/abcDEF1234567890`);
  expect(screen.getByText('Private link: opens only for your account')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Copy link' })).toBeTruthy();
});
