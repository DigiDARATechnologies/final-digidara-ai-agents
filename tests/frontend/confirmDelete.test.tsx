import { fireEvent, render, screen } from '@testing-library/react';
import ConfirmDialog from '../../src/components/ConfirmDialog';
import Sidebar from '../../src/components/Sidebar';
import SettingsModal from '../../src/components/SettingsModal';

jest.mock('../../src/lib/usageApi', () => ({ fetchAllUsageSummaries: jest.fn().mockResolvedValue([]) }));
jest.mock('../../src/components/BillingPanel', () => ({ __esModule: true, default: () => null }));
jest.mock('../../src/components/SettingsExtras', () => ({ AppearanceSettings: () => null, SecuritySettings: () => null }));
jest.mock('../../src/lib/communicationApi', () => ({ bridgeIdentity: jest.fn(), getDashboard: jest.fn(), getHistory: jest.fn() }));

describe('ConfirmDialog', () => {
  test('confirms, cancels, and Escape cancels', () => {
    const onConfirm = jest.fn(); const onCancel = jest.fn();
    render(<ConfirmDialog title="Delete this chat?" message="Sure?" confirmLabel="Delete" onConfirm={onConfirm} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalledTimes(2);
  });
});

describe('Settings: clear chat history', () => {
  const user = { id: 'u', name: 'A', email: 'a@x.y', mobile: '1', initial: 'A' };
  const open = (onClearHistory: jest.Mock) => render(
    <SettingsModal open user={user} chats={[]} glowOn onClose={jest.fn()} onOpenChat={jest.fn()} onGlowToggle={jest.fn()}
      onClearHistory={onClearHistory} onToast={jest.fn()} onExportData={jest.fn()} onDeleteAccount={jest.fn()} />,
  );

  test('asks first; nothing is cleared until confirmed', () => {
    const clear = jest.fn();
    open(clear);
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect(clear).not.toHaveBeenCalled();
    expect(screen.getByText('Clear all chat history?')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(clear).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    fireEvent.click(screen.getByRole('button', { name: 'Clear all' }));
    expect(clear).toHaveBeenCalledTimes(1);
  });
});

describe('Sidebar: delete chat', () => {
  const user = { id: 'u', name: 'A', email: 'a@x.y', mobile: '1', initial: 'A' };
  const chat = { id: 'c1', agentId: 'capstone-project', title: 'portfolio website', messages: [], updatedAt: 1 };
  const renderSidebar = (onDeleteChat: jest.Mock) => render(
    <Sidebar theme="light" planName="Basic" user={user} collapsed={false} mobileOpen={false} homeActive={false} chats={[chat]} currentChatId={null}
      userMenuOpen={false} openChatMenuId="c1" onToggleCollapse={jest.fn()} onCloseMobile={jest.fn()} onNewChat={jest.fn()} onGoHome={jest.fn()} onOpenChat={jest.fn()}
      onOpenHelpPage={jest.fn()} onNavAction={jest.fn()} onToggleUserMenu={jest.fn()} onUserMenuAction={jest.fn()} onToggleChatMenu={jest.fn()}
      onRenameChat={jest.fn()} onTogglePinChat={jest.fn()} onDeleteChat={onDeleteChat} />,
  );
  const openMenu = () => fireEvent.click(screen.getByRole('button', { name: 'Chat options' }));

  test('Delete asks first, names the chat, and only deletes on confirm', () => {
    const onDeleteChat = jest.fn();
    renderSidebar(onDeleteChat);
    openMenu();
    fireEvent.click(screen.getByRole('menuitem', { name: /Delete/ }));
    expect(onDeleteChat).not.toHaveBeenCalled();
    expect(screen.getByText('Delete this chat?')).toBeInTheDocument();
    expect(screen.getByText(/"portfolio website" and its messages will be deleted/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(onDeleteChat).toHaveBeenCalledWith('c1');
    expect(screen.queryByText('Delete this chat?')).toBeNull();
  });

  test('Cancel keeps the chat', () => {
    const onDeleteChat = jest.fn();
    renderSidebar(onDeleteChat);
    openMenu();
    fireEvent.click(screen.getByRole('menuitem', { name: /Delete/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onDeleteChat).not.toHaveBeenCalled();
    expect(screen.queryByText('Delete this chat?')).toBeNull();
  });
});

describe('Settings: agent chats list', () => {
  test('lists only the built agents, not the placeholder cards', () => {
    const user = { id: 'u', name: 'A', email: 'a@x.y', mobile: '1', initial: 'A' };
    render(
      <SettingsModal open user={user} chats={[]} glowOn initialTab="agent-chats" onClose={jest.fn()} onOpenChat={jest.fn()} onGlowToggle={jest.fn()}
        onClearHistory={jest.fn()} onToast={jest.fn()} onExportData={jest.fn()} onDeleteAccount={jest.fn()} />,
    );
    for (const name of ['Capstone Project Agent', 'LeetCode / DSA Agent', 'Resume Builder Agent', 'Aptitude Trainer Agent']) {
      expect(screen.getByText(name)).toBeInTheDocument();
    }
    for (const name of ['Research Agent', 'Career Guidance Agent', 'Content Writer Agent', 'Data Analyst Agent', 'Video AI Agent', 'Business Strategy Agent', 'Coding Assistant Agent']) {
      expect(screen.queryByText(name)).toBeNull();
    }
    expect(screen.getByText('8 agents')).toBeInTheDocument();
  });
});
