import { fireEvent, render, screen } from '@testing-library/react';
import NewChatLanding from '../../src/components/NewChatLanding';

const mockStart = jest.fn();
const mockStop = jest.fn();
let mockSupported = true;
let mockListening = false;

jest.mock('../../src/hooks/useSpeechRecognition', () => ({
  __esModule: true,
  default: () => ({ supported: mockSupported, listening: mockListening, error: '', start: mockStart, stop: mockStop }),
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockSupported = true;
  mockListening = false;
});

test('typing and submitting sends the trimmed text', () => {
  const onSend = jest.fn();
  render(<NewChatLanding onSend={onSend} onAttachClick={jest.fn()} />);
  fireEvent.change(screen.getByPlaceholderText('Ask anything'), { target: { value: '  hello there  ' } });
  fireEvent.submit(screen.getByPlaceholderText('Ask anything').closest('form')!);
  expect(onSend).toHaveBeenCalledWith('hello there');
});

test('the attach button calls onAttachClick instead of silently doing nothing', () => {
  const onAttachClick = jest.fn();
  render(<NewChatLanding onSend={jest.fn()} onAttachClick={onAttachClick} />);
  fireEvent.click(screen.getByTitle('Attach file'));
  expect(onAttachClick).toHaveBeenCalledTimes(1);
});

test('the mic button starts voice capture, which fills the textarea', () => {
  mockStart.mockImplementation((onTranscript: (text: string) => void) => onTranscript('dictated text'));
  render(<NewChatLanding onSend={jest.fn()} onAttachClick={jest.fn()} />);
  fireEvent.click(screen.getByTitle('Voice input'));
  expect(mockStart).toHaveBeenCalledTimes(1);
  expect(screen.getByPlaceholderText('Ask anything')).toHaveValue('dictated text');
});

test('clicking the mic again while listening stops it instead of starting a second session', () => {
  mockListening = true;
  render(<NewChatLanding onSend={jest.fn()} onAttachClick={jest.fn()} />);
  fireEvent.click(screen.getByTitle('Stop recording'));
  expect(mockStop).toHaveBeenCalledTimes(1);
  expect(mockStart).not.toHaveBeenCalled();
});

test('the mic button is hidden entirely when the browser has no speech recognition support', () => {
  mockSupported = false;
  render(<NewChatLanding onSend={jest.fn()} onAttachClick={jest.fn()} />);
  expect(screen.queryByTitle('Voice input')).not.toBeInTheDocument();
});
