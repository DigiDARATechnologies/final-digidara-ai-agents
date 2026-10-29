import { fireEvent, render, screen, within } from '@testing-library/react';
import Sidebar from '../../src/components/Sidebar';

const user = { id: 'u', name: 'A', email: 'a@x.y', mobile: '1', initial: 'A' };

function renderSidebar(inOrganization: boolean, handlers: { onGoHome?: jest.Mock } = {}) {
  return render(
    <Sidebar theme="light" planName="Basic" user={user} collapsed={false} mobileOpen={false} homeActive={false} inOrganization={inOrganization}
      chats={[]} currentChatId={null} userMenuOpen={false} openChatMenuId={null} onToggleCollapse={jest.fn()} onCloseMobile={jest.fn()}
      onNewChat={jest.fn()} onGoHome={handlers.onGoHome ?? jest.fn()} onOpenChat={jest.fn()} onOpenHelpPage={jest.fn()} onNavAction={jest.fn()}
      onToggleUserMenu={jest.fn()} onUserMenuAction={jest.fn()} onToggleChatMenu={jest.fn()} onRenameChat={jest.fn()}
      onTogglePinChat={jest.fn()} onDeleteChat={jest.fn()} />,
  );
}

test('the sidebar has My Dashboard, and no SkillDARA Agents or Settings items', () => {
  const { container } = renderSidebar(true);
  const nav = within(container.querySelector('.nav-list') as HTMLElement);
  expect(nav.getByRole('button', { name: 'My Dashboard' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'SkillDARA Agents' })).not.toBeInTheDocument();
  expect(nav.queryByRole('button', { name: 'Settings' })).not.toBeInTheDocument();   // still in the profile menu
});

test('Assessments show only for an organization member', () => {
  const { unmount } = renderSidebar(false);
  expect(screen.queryByRole('button', { name: 'Assessments' })).not.toBeInTheDocument();
  unmount();
  renderSidebar(true);
  expect(screen.getByRole('button', { name: 'Assessments' })).toBeInTheDocument();
});

test('the logo goes home', () => {
  const onGoHome = jest.fn();
  renderSidebar(false, { onGoHome });
  fireEvent.click(screen.getByRole('button', { name: 'SkillDARA agents home' }));
  expect(onGoHome).toHaveBeenCalled();
});
