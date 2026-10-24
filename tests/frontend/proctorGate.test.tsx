/** The proctoring screen: nothing starts before consent; warnings end the test. */
jest.mock('../../src/lib/proctorApi', () => ({
  startProctoring: jest.fn(), fetchProctorState: jest.fn(), sendProctorEvents: jest.fn(), sendProctorSnapshot: jest.fn(),
}));

import { act, fireEvent, render, screen } from '@testing-library/react';
import ProctorGate from '../../src/components/ProctorGate';
import * as api from '../../src/lib/proctorApi';

const settings = { tab: true, fullscreen: true, copy_paste: true, webcam: true, face: true, max_warnings: 1 };
const state = (extra = {}) => ({
  id: 's1', agent_name: 'mock_interview_agent', ref: '9', assessment_id: null, settings, status: 'active',
  warnings: 0, max_warnings: 1, warnings_left: 1, integrity: 100, terminated: false, ...extra,
});

beforeEach(() => {
  jest.clearAllMocks();
  const track = { stop: jest.fn(), onended: null };
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: jest.fn().mockResolvedValue({
      getTracks: () => [track], getVideoTracks: () => [track], getAudioTracks: () => [], removeTrack: jest.fn(),
    }) },
  });
});

test('the test is hidden until the learner agrees, then proctoring starts', async () => {
  (api.startProctoring as jest.Mock).mockResolvedValue(state());
  render(<ProctorGate agentName="mock_interview_agent" refId="9" label="Hard interview" onTerminate={jest.fn()}><p>Question 1</p></ProctorGate>);

  expect(screen.queryByText('Question 1')).toBeNull();
  const start = screen.getByRole('button', { name: /start/i });
  expect(start).toBeDisabled();
  expect(api.startProctoring).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('checkbox'));
  await act(async () => { fireEvent.click(start); });

  expect(api.startProctoring).toHaveBeenCalledWith('mock_interview_agent', '9');
  expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();
  expect(screen.getByText('Question 1')).toBeInTheDocument();
  expect(screen.getByText(/Warnings 0\/1/)).toBeInTheDocument();
});

test('copy is blocked, and too many warnings end the test', async () => {
  (api.startProctoring as jest.Mock).mockResolvedValue(state());
  (api.sendProctorEvents as jest.Mock)
    .mockResolvedValueOnce(state({ integrity: 97 }))
    .mockResolvedValueOnce(state({ warnings: 2, status: 'terminated', terminated: true, warnings_left: 0 }));
  const onTerminate = jest.fn();
  render(<ProctorGate agentName="mock_interview_agent" refId="9" label="Hard interview" onTerminate={onTerminate}><p>Question 1</p></ProctorGate>);
  fireEvent.click(screen.getByRole('checkbox'));
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /start/i })); });

  const copy = new Event('copy', { bubbles: true, cancelable: true });
  await act(async () => { document.dispatchEvent(copy); });
  expect(copy.defaultPrevented).toBe(true);
  expect(api.sendProctorEvents).toHaveBeenCalledWith('s1', [{ kind: 'copy', detail: '' }]);

  // Leaving the window right after starting is the browser settling in: not counted.
  await act(async () => { window.dispatchEvent(new Event('blur')); });
  expect(api.sendProctorEvents).toHaveBeenCalledTimes(1);
  window.dispatchEvent(new Event('focus'));
  const realNow = Date.now;
  Date.now = () => realNow() + 5_000;
  await act(async () => { window.dispatchEvent(new Event('blur')); });
  Date.now = realNow;
  expect(api.sendProctorEvents).toHaveBeenLastCalledWith('s1', [expect.objectContaining({ kind: 'focus_lost' })]);
  expect(onTerminate).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/The test has ended/)).toBeInTheDocument();
  expect(screen.queryByText('Question 1')).toBeNull();
});

test('a camera that is blocked is explained and the test does not start', async () => {
  (api.startProctoring as jest.Mock).mockResolvedValue(state());
  (navigator.mediaDevices.getUserMedia as jest.Mock).mockRejectedValue(Object.assign(new Error('no'), { name: 'NotAllowedError' }));
  render(<ProctorGate agentName="capstone_project_agent" refId="sub:1" label="Capstone viva" onTerminate={jest.fn()}><p>Viva Q</p></ProctorGate>);
  fireEvent.click(screen.getByRole('checkbox'));
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /start/i })); });
  expect(screen.getByRole('alert')).toHaveTextContent(/Camera access was blocked/);
  expect(screen.queryByText('Viva Q')).toBeNull();
});
