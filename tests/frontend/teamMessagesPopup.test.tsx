jest.mock('../../src/lib/learnerApi', () => ({ fetchTeamMessages: jest.fn(), markTeamMessagesRead: jest.fn().mockResolvedValue({ marked: 1 }) }));

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import TeamMessagesPopup from '../../src/components/TeamMessagesPopup';
import * as learnerApi from '../../src/lib/learnerApi';

const api = jest.mocked(learnerApi);

test('unread team messages open by themselves and closing marks them read', async () => {
  api.fetchTeamMessages.mockResolvedValue({ messages: [
    { id: 'm2', report_id: 'r1', report_message: 'why is my report not generated?', body: 'It is fixed now.', created_at: '2026-11-11T10:00:00', read_at: null },
    { id: 'm1', report_id: null, body: 'An old note', created_at: '2026-11-01T10:00:00', read_at: '2026-11-02T10:00:00' },
  ] });
  render(<TeamMessagesPopup userId="u1" />);
  expect(await screen.findByText('It is fixed now.', undefined, { timeout: 5000 })).toBeTruthy();
  expect(screen.getByText(/why is my report not generated/)).toBeTruthy();
  expect(screen.queryByText('An old note')).toBeNull();
  fireEvent.click(screen.getByText('OK, got it'));
  await waitFor(() => expect(api.markTeamMessagesRead).toHaveBeenCalled(), { timeout: 5000 });
  expect(screen.queryByText('It is fixed now.')).toBeNull();
});

test('nothing shows when every message is read', async () => {
  api.fetchTeamMessages.mockResolvedValue({ messages: [] });
  const { container } = render(<TeamMessagesPopup userId="u1" />);
  await waitFor(() => expect(api.fetchTeamMessages).toHaveBeenCalled());
  expect(container.innerHTML).toBe('');
});
