import { fireEvent, render, screen } from '@testing-library/react';
import Topbar from '../../src/components/Topbar';
import type { PendingNotification } from '../../src/lib/notifications';

const user = { id: 'u', name: 'A', email: 'a@x.y', mobile: '1', initial: 'A' };
const note = (over: Partial<PendingNotification> = {}): PendingNotification => ({
  key: 'c1:awaiting_submission', id: 'c1', chatId: 'c1', icon: '🎓', agentName: 'Capstone Project Agent', body: 'Your project is pending submission.', ...over,
});

function renderBar(notifications: PendingNotification[], handlers: { open?: jest.Mock; dismiss?: jest.Mock } = {}) {
  return render(
    <Topbar title="t" user={user} notifOpen dashboardAvailable={false} dashboardOpen={false} onToggleDashboard={jest.fn()} systemOnline
      theme="light" onToggleTheme={jest.fn()} onToggleMobileMenu={jest.fn()} onToggleNotif={jest.fn()}
      notifications={notifications} onOpenNotification={handlers.open ?? jest.fn()} onDismissNotification={handlers.dismiss ?? jest.fn()} />,
  );
}

test('each notification has a dismiss X that dismisses it without opening the chat', () => {
  const open = jest.fn(); const dismiss = jest.fn();
  renderBar([note(), note({ key: 'r:x', id: 'r', chatId: 'r', agentName: 'Resume Builder Agent', body: 'Your resume is in progress.' })], { open, dismiss });
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss Capstone Project Agent notification' }));
  expect(dismiss).toHaveBeenCalledWith(expect.objectContaining({ key: 'c1:awaiting_submission' }));
  expect(open).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Your project is pending submission.'));
  expect(open).toHaveBeenCalledWith(expect.objectContaining({ chatId: 'c1' }));
});

test('nothing pending: caught-up line, no red dot, no dismiss buttons', () => {
  const { container } = renderBar([]);
  expect(screen.getByText("You're all caught up")).toBeInTheDocument();
  expect(container.querySelector('.badge-dot')).toBeNull();
  expect(screen.queryByRole('button', { name: /Dismiss/ })).toBeNull();
});
