jest.mock('../../src/lib/orchestratorApi', () => ({ transcribeGeneralAudio: jest.fn(), warmBoss: jest.fn() }));
jest.mock('../../src/lib/voiceEngine', () => ({ speakNatural: jest.fn((_t: string, h?: { onEnd?: () => void }) => { h?.onEnd?.(); return Promise.resolve(true); }), stopSpeaking: jest.fn() }));
let mockRecordingSupported = true;
jest.mock('../../src/lib/voiceCapture', () => ({ audioRecordingSupported: () => mockRecordingSupported }));
import { fireEvent, render, screen } from '@testing-library/react';
import NewChatLanding from '../../src/components/NewChatLanding';

const mockStart = jest.fn();
const mockStop = jest.fn();
let mockSupported = true;
let mockListening = false;

jest.mock('../../src/hooks/useSpeechRecognition', () => ({
  __esModule: true,
  default: () => ({ supported: mockSupported, listening: mockListening, transcribing: false, error: '', start: mockStart, stop: mockStop, cancel: jest.fn() }),
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockSupported = true;
  mockListening = false;
});

test('typing and submitting sends the trimmed text', () => {
  const onSend = jest.fn();
  render(<NewChatLanding onSend={onSend} onAttachClick={jest.fn()} onOpenAgent={jest.fn()} />);
  fireEvent.change(screen.getByLabelText('Message'), { target: { value: '  hello there  ' } });
  fireEvent.submit(screen.getByLabelText('Message').closest('form')!);
  expect(onSend).toHaveBeenCalledWith('hello there');
});

test('the attach button calls onAttachClick instead of silently doing nothing', () => {
  const onAttachClick = jest.fn();
  render(<NewChatLanding onSend={jest.fn()} onAttachClick={onAttachClick} onOpenAgent={jest.fn()} />);
  fireEvent.click(screen.getByTitle('Attach file'));
  expect(onAttachClick).toHaveBeenCalledTimes(1);
});

test('the mic opens a voice conversation; its first question starts the chat', () => {
  const onSend = jest.fn();
  render(<NewChatLanding onSend={onSend} onAttachClick={jest.fn()} onOpenAgent={jest.fn()} />);
  fireEvent.click(screen.getByTitle('Talk with Boss'));
  expect(screen.getByRole('dialog', { name: 'Voice conversation with Boss' })).toBeInTheDocument();
  expect(mockStart).toHaveBeenCalledTimes(1);
  mockStart.mock.calls[0][0]('What can DigiDARA do?', true);
  expect(onSend).toHaveBeenCalledWith('What can DigiDARA do?');
});

test('the mic button is hidden when the browser cannot record audio', () => {
  mockRecordingSupported = false;
  render(<NewChatLanding onSend={jest.fn()} onAttachClick={jest.fn()} onOpenAgent={jest.fn()} />);
  expect(screen.queryByTitle('Talk with Boss')).not.toBeInTheDocument();
  mockRecordingSupported = true;
});

test('the agent chips under the message box start a chat with that agent', () => {
  const onOpenAgent = jest.fn();
  render(<NewChatLanding onSend={jest.fn()} onAttachClick={jest.fn()} onOpenAgent={onOpenAgent} />);
  fireEvent.click(screen.getByRole('button', { name: /Aptitude Trainer/ }));
  expect(onOpenAgent).toHaveBeenCalledWith('aptitude');
});

test('the agent menu in the message box opens the chosen agent', () => {
  const onOpenAgent = jest.fn();
  render(<NewChatLanding onSend={jest.fn()} onAttachClick={jest.fn()} onOpenAgent={onOpenAgent} />);
  fireEvent.click(screen.getByRole('button', { name: /Auto-select agent/ }));
  fireEvent.click(screen.getByRole('menuitem', { name: /Mock Interview/ }));
  expect(onOpenAgent).toHaveBeenCalledWith('mock-interview');
  expect(screen.queryByRole('menu')).not.toBeInTheDocument();
});
