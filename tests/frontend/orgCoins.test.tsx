jest.mock('../../src/lib/orgApi', () => ({
  fetchPlatformOrgs: jest.fn(), platformCreateOrg: jest.fn(), platformUpdateOrg: jest.fn(), platformGiveCoins: jest.fn(), platformDeleteOrg: jest.fn(),
}));
jest.mock('../../src/components/org/OrgDashboard', () => ({ __esModule: true, default: () => null }));
jest.mock('../../src/components/org/OrgAssistant', () => ({ __esModule: true, default: () => null }));

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import OrganizationsPanel from '../../src/components/admin/OrganizationsPanel';
import * as orgApi from '../../src/lib/orgApi';

const api = jest.mocked(orgApi);
const org = { id: 'o1', name: 'ABC College', kind: 'college', member_limit: 0, member_count: 3, status: 'active' as const, created_at: null,
  active_codes: 1, admins: [{ name: 'Meena', email: 'meena@abc.edu' }], admin_coins: 100, staff_coins: 50, student_coins: 20 };

test('a new organization is created with coins for its admin, each staff login and each student', async () => {
  api.fetchPlatformOrgs.mockResolvedValue([]);
  api.platformCreateOrg.mockResolvedValue({ organization: org, admin: { name: 'Meena', email: 'meena@abc.edu', status: 'created', temporary_password: 'pw12345678', coins: 100 } });
  render(<OrganizationsPanel />);
  fireEvent.change(screen.getByPlaceholderText('e.g. ABC Engineering College'), { target: { value: 'ABC College' } });
  fireEvent.change(screen.getByPlaceholderText('placement@college.edu'), { target: { value: 'meena@abc.edu' } });
  fireEvent.change(screen.getByLabelText('For the admin'), { target: { value: '100' } });
  fireEvent.change(screen.getByLabelText('For each staff login'), { target: { value: '50' } });
  fireEvent.change(screen.getByLabelText('For each student'), { target: { value: '20' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create organization' }));
  await waitFor(() => expect(api.platformCreateOrg).toHaveBeenCalledWith(expect.objectContaining({ admin_coins: 100, staff_coins: 50, student_coins: 20 })));
  expect(await screen.findByText('100 coins given to the admin.')).toBeInTheDocument();
});

test('an organization is edited (name, type, limit, coins) and coins given to its current members', async () => {
  api.fetchPlatformOrgs.mockResolvedValue([org]);
  api.platformUpdateOrg.mockResolvedValue({ ...org, student_coins: 30 });
  api.platformGiveCoins.mockResolvedValue({ people: 2, coins: 60 });
  render(<OrganizationsPanel />);
  expect(await screen.findByText('Coins: admin 100 · staff 50 · student 20')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
  const item = within(screen.getByText('ABC College').closest('li') as HTMLElement);
  fireEvent.change(item.getByDisplayValue('ABC College'), { target: { value: 'ABC Engineering College' } });
  fireEvent.change(item.getByLabelText('For each student'), { target: { value: '30' } });
  fireEvent.click(item.getByRole('button', { name: 'Save and give now' }));
  await waitFor(() => expect(api.platformGiveCoins).toHaveBeenCalledWith('o1'));
  expect(api.platformUpdateOrg).toHaveBeenCalledWith('o1', {
    name: 'ABC Engineering College', kind: 'college', member_limit: 0, admin_coins: 100, staff_coins: 50, student_coins: 30,
  });
  expect(await screen.findByText('60 coins given to 2 people.')).toBeInTheDocument();
});

test('deleting needs the name typed and says how many members were released', async () => {
  api.fetchPlatformOrgs.mockResolvedValue([org]);
  api.platformDeleteOrg.mockResolvedValue({ deleted: 'o1', name: 'ABC College', members_released: 3 });
  const prompt = jest.spyOn(window, 'prompt');
  render(<OrganizationsPanel />);
  await screen.findByText('ABC College');
  prompt.mockReturnValueOnce('wrong name');
  fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
  expect(await screen.findByText("The name didn't match, so nothing was deleted.")).toBeInTheDocument();
  expect(api.platformDeleteOrg).not.toHaveBeenCalled();
  prompt.mockReturnValueOnce('ABC College');
  fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(api.platformDeleteOrg).toHaveBeenCalledWith('o1'));
  expect(await screen.findByText('ABC College deleted. 3 members released.')).toBeInTheDocument();
  prompt.mockRestore();
});
