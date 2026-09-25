const mockPreview = jest.fn();
const mockConfirm = jest.fn();
const mockDownload = jest.fn();
jest.mock('../../src/lib/capstoneApi', () => ({
  downloadFinalReport: jest.fn(),
  previewCertificate: (...args: unknown[]) => mockPreview(...args),
  confirmCertificate: (...args: unknown[]) => mockConfirm(...args),
  downloadCertificate: (...args: unknown[]) => mockDownload(...args),
}));

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AgentDashboard from '../../src/components/AgentDashboard';
import type { CapstoneFlowState } from '../../src/lib/capstoneFlow';

const user = { id: 'u1', name: 'Asha Rao', email: 'asha@example.com', mobile: '9999999999', initial: 'A' };
const graded: CapstoneFlowState = {
  step: 'graded', name: 'Asha', email: 'a@example.com', phone: '', difficulty: 'easy',
  passed: true, finalScore: 88, vivaSubmissionId: 'sub-42',
};

const shown = (name: string, confirmed = false) => ({
  name, project_title: 'Inventory Tracker', certificate_id: 'DDT-CAP-2026-SUB42', confirmed, editable: !confirmed,
  content_type: 'image/jpeg', preview: 'AAAA',
});

const open = () => render(<AgentDashboard user={user} state={graded} onClose={jest.fn()} />);
const nameBox = () => screen.getByLabelText('Name on the certificate') as HTMLInputElement;
const okButton = () => screen.getByRole('button', { name: 'OK' });

beforeEach(() => { mockPreview.mockReset(); mockConfirm.mockReset(); mockDownload.mockReset(); });

test('the certificate section appears only once the score and the viva are both passed', () => {
  const { rerender } = render(<AgentDashboard user={user} state={{ ...graded, passed: false }} onClose={jest.fn()} />);
  expect(screen.queryByText('Your certificate')).toBeNull();
  rerender(<AgentDashboard user={user} state={{ ...graded, step: 'awaiting_viva_answer' }} onClose={jest.fn()} />);
  expect(screen.queryByText('Your certificate')).toBeNull();
  rerender(<AgentDashboard user={user} state={{ ...graded, vivaSubmissionId: null }} onClose={jest.fn()} />);
  expect(screen.queryByText('Your certificate')).toBeNull();
  rerender(<AgentDashboard user={user} state={graded} onClose={jest.fn()} />);
  expect(screen.getByText('Your certificate')).toBeInTheDocument();
});

test('previewing shows the certificate and the name, editable, with no download yet', async () => {
  mockPreview.mockResolvedValue(shown('Asha Rao'));
  open();
  fireEvent.click(screen.getByRole('button', { name: 'Preview my certificate' }));
  const image = await screen.findByAltText('Certificate for Asha Rao: Inventory Tracker');
  expect(image).toHaveAttribute('src', 'data:image/jpeg;base64,AAAA');
  expect(mockPreview).toHaveBeenCalledWith('sub-42', undefined);
  expect(nameBox().value).toBe('Asha Rao');
  expect(screen.queryByRole('button', { name: /Download certificate/ })).toBeNull();   // not before OK
});

test('editing the name needs an updated preview before OK -- what is approved is what was seen', async () => {
  mockPreview.mockResolvedValueOnce(shown('Asha Rao')).mockResolvedValueOnce(shown('Asha Rao Iyer'));
  open();
  fireEvent.click(screen.getByRole('button', { name: 'Preview my certificate' }));
  await screen.findByAltText(/Certificate for Asha Rao:/);
  expect(okButton()).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Update preview' })).toBeDisabled();       // nothing changed yet

  fireEvent.change(nameBox(), { target: { value: 'Asha Rao Iyer' } });
  expect(okButton()).toBeDisabled();                                                   // not previewed yet
  fireEvent.click(screen.getByRole('button', { name: 'Update preview' }));
  await screen.findByAltText(/Certificate for Asha Rao Iyer:/);
  expect(mockPreview).toHaveBeenLastCalledWith('sub-42', 'Asha Rao Iyer');
  expect(okButton()).toBeEnabled();
});

test('OK issues the certificate, locks the name, and then the PDF can be downloaded', async () => {
  mockPreview.mockResolvedValueOnce(shown('Asha Rao')).mockResolvedValueOnce(shown('Asha Rao', true));
  mockConfirm.mockResolvedValue({ name: 'Asha Rao', certificate_id: 'DDT-CAP-2026-SUB42', confirmed: true, editable: false });
  mockDownload.mockResolvedValue(undefined);
  open();
  fireEvent.click(screen.getByRole('button', { name: 'Preview my certificate' }));
  await screen.findByAltText(/Certificate for Asha Rao:/);
  fireEvent.click(okButton());

  const download = await screen.findByRole('button', { name: 'Download certificate (PDF)' });
  expect(mockConfirm).toHaveBeenCalledWith('sub-42', 'Asha Rao');
  expect(screen.getByText(/The name can no longer be changed/)).toBeInTheDocument();
  expect(screen.getByText(/DDT-CAP-2026-SUB42/)).toBeInTheDocument();
  expect(screen.queryByLabelText('Name on the certificate')).toBeNull();               // no editing after OK
  expect(screen.queryByRole('button', { name: 'OK' })).toBeNull();

  fireEvent.click(download);
  await waitFor(() => expect(mockDownload).toHaveBeenCalledWith('sub-42'));
});

test('a rejected name (or any failure) is shown, and nothing is issued', async () => {
  mockPreview.mockResolvedValue(shown('Asha Rao'));
  mockConfirm.mockRejectedValue(new Error('Use letters, spaces, dots, hyphens or apostrophes only (English/Latin letters).'));
  open();
  fireEvent.click(screen.getByRole('button', { name: 'Preview my certificate' }));
  await screen.findByAltText(/Certificate for Asha Rao:/);
  fireEvent.click(okButton());
  expect(await screen.findByRole('alert')).toHaveTextContent('Use letters, spaces');
  expect(screen.queryByRole('button', { name: /Download certificate/ })).toBeNull();
  expect(okButton()).toBeEnabled();                                                     // can correct and retry
});

test('a certificate that was already issued opens locked, ready to download', async () => {
  mockPreview.mockResolvedValue(shown('Asha Rao', true));
  open();
  fireEvent.click(screen.getByRole('button', { name: 'Preview my certificate' }));
  expect(await screen.findByRole('button', { name: 'Download certificate (PDF)' })).toBeInTheDocument();
  expect(screen.queryByLabelText('Name on the certificate')).toBeNull();
});
