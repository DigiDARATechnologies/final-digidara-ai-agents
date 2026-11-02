const mockDownload = jest.fn();
jest.mock('../../src/lib/capstoneApi', () => ({ downloadFinalReport: (...args: unknown[]) => mockDownload(...args) }));

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AgentDashboard from '../../src/components/AgentDashboard';
import type { CapstoneFlowState } from '../../src/lib/capstoneFlow';

const user = { id: 'u1', name: 'Asha Rao', email: 'asha@example.com', mobile: '9999999999', initial: 'A' };
const graded: CapstoneFlowState = {
  step: 'graded', name: 'Asha', email: 'a@example.com', phone: '', difficulty: 'easy',
  passed: true, finalScore: 88, vivaSubmissionId: 'sub-42',
};

beforeEach(() => mockDownload.mockReset());

test('a graded project says its files were submitted, and a passed one shows no old revision request', () => {
  const { container, rerender } = render(<AgentDashboard user={user} state={{ ...graded, revisionNotes: 'Fix the missing module.' } as CapstoneFlowState} agentKind="capstone" />);
  expect(screen.getByText('Submitted')).toBeTruthy();
  expect(screen.queryByText('Not uploaded')).toBeNull();
  expect(container.textContent).not.toContain('Revision Requested');
  rerender(<AgentDashboard user={user} state={{ ...graded, passed: false, finalScore: 55, revisionNotes: 'Fix the missing module.' } as CapstoneFlowState} agentKind="capstone" />);
  expect(container.textContent).toContain('Revision Requested');
});

test('the dashboard offers the final report once the score and the viva are passed', async () => {
  mockDownload.mockResolvedValue(undefined);
  render(<AgentDashboard user={user} state={graded} onClose={jest.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: 'Download final report (PDF)' }));
  await waitFor(() => expect(mockDownload).toHaveBeenCalledWith('sub-42'));
});

test('no report button before that: failed, not graded yet, or no submission on record', () => {
  const { rerender } = render(<AgentDashboard user={user} state={{ ...graded, passed: false }} onClose={jest.fn()} />);
  expect(screen.queryByRole('button', { name: /final report/i })).toBeNull();
  rerender(<AgentDashboard user={user} state={{ ...graded, step: 'awaiting_submission' }} onClose={jest.fn()} />);
  expect(screen.queryByRole('button', { name: /final report/i })).toBeNull();
  rerender(<AgentDashboard user={user} state={{ ...graded, vivaSubmissionId: null }} onClose={jest.fn()} />);
  expect(screen.queryByRole('button', { name: /final report/i })).toBeNull();
});

test('a failed download shows the reason instead of failing silently', async () => {
  mockDownload.mockRejectedValue(new Error('The final report is unavailable.'));
  render(<AgentDashboard user={user} state={graded} onClose={jest.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: 'Download final report (PDF)' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('The final report is unavailable.');
  expect(screen.getByRole('button', { name: 'Download final report (PDF)' })).toBeEnabled();   // can retry
});
