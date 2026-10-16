const mockOpenChat = jest.fn();
const mockCheck = jest.fn();
const mockDownload = jest.fn();
jest.mock('../../src/lib/linksApi', () => ({
  openSharedChat: (token: string) => mockOpenChat(token),
  checkCertificateLink: (token: string) => mockCheck(token),
  downloadCertificateLink: (token: string) => mockDownload(token),
}));
import { act, fireEvent, render, screen } from '@testing-library/react';
import SharedLinkView from '../../src/components/SharedLinkView';

beforeEach(() => {
  mockOpenChat.mockReset();
  mockCheck.mockReset();
  mockDownload.mockReset();
});

test('a shared chat opens read-only with who shared it', async () => {
  mockOpenChat.mockResolvedValue({
    title: 'Aptitude practice', agent_id: 'aptitude', mode: 'public', is_owner: false, owner_name: 'Priya', chat_id: null,
    messages: [{ role: 'user', text: 'Start a test', time: '10:00' }],
  });
  await act(async () => { render(<SharedLinkView link={{ kind: 'chat', token: 'tok' }} onClose={jest.fn()} />); });
  expect(screen.getByText('Aptitude practice')).toBeTruthy();
  expect(screen.getByText('Shared by Priya. Read only.')).toBeTruthy();
  expect(screen.getByText('Start a test')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Open this chat' })).toBeNull();
});

test('a private link opened by another account shows why it cannot open', async () => {
  mockOpenChat.mockRejectedValue(new Error('This chat link is private.'));
  await act(async () => { render(<SharedLinkView link={{ kind: 'chat', token: 'tok' }} onClose={jest.fn()} />); });
  expect(screen.getByRole('alert').textContent).toBe('This chat link is private.');
});

test('the certificate owner downloads; an expired link says so', async () => {
  mockCheck.mockResolvedValue(undefined);
  mockDownload.mockResolvedValue({ blob: new Blob(['%PDF']), filename: 'certificate.pdf' });
  const createUrl = jest.fn(() => 'blob:1');
  Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: jest.fn() });
  await act(async () => { render(<SharedLinkView link={{ kind: 'certificate', token: 'tok' }} onClose={jest.fn()} />); });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Download certificate (PDF)' })); });
  expect(mockDownload).toHaveBeenCalledWith('tok');
  expect(createUrl).toHaveBeenCalled();
  expect(screen.getByRole('button', { name: 'Download again' })).toBeTruthy();

  mockDownload.mockRejectedValue(new Error('This certificate link has expired (links last 5 minutes). Ask Boss for a new one.'));
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Download again' })); });
  expect(screen.getByRole('alert').textContent).toContain('expired');
});
