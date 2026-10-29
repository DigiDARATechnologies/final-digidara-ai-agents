jest.mock('../../src/lib/orgApi', () => ({ fetchStaff: jest.fn(), addStaff: jest.fn(), updateStaff: jest.fn(), fetchFilteredMembers: jest.fn() }));jest.mock('../../src/lib/learnerApi', () => ({ removeOrgMember: jest.fn(), BAND_TONE: { not_started: 'muted', not_ready: 'low', developing: 'mid', almost_ready: 'good', job_ready: 'top' } }));jest.mock('../../src/components/ReadinessView', () => ({ ScoreRing: ({ score }: { score: number | null }) => <span>ring {score ?? '-'}</span> }));

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import StaffPanel from '../../src/components/org/StaffPanel';
import * as orgApi from '../../src/lib/orgApi';

const api = jest.mocked(orgApi);
const options = { department: ['Computer Science'], year: ['2nd year'], section: ['A'] };

test('a staff login is created with department, degree, year, section and class head', async () => {
  api.fetchStaff.mockResolvedValue([]);
  api.addStaff.mockResolvedValue({ name: 'Priya', email: 'priya@college.edu', status: 'created', temporary_password: 'x1y2z3w4v5' });
  render(<StaffPanel orgId="org" options={options} onToast={jest.fn()} />);
  fireEvent.change(screen.getByPlaceholderText('e.g. Priya (Placement cell)'), { target: { value: 'Priya' } });
  fireEvent.change(screen.getByPlaceholderText('priya@college.edu'), { target: { value: 'priya@college.edu' } });
  fireEvent.change(screen.getByLabelText(/^Department/), { target: { value: 'Computer Science' } });
  fireEvent.change(screen.getByLabelText(/^Year/), { target: { value: '2nd year' } });
  fireEvent.change(screen.getByLabelText(/^Section/), { target: { value: 'A' } });
  fireEvent.change(screen.getByPlaceholderText('e.g. B.E.'), { target: { value: 'B.E.' } });
  fireEvent.click(screen.getByLabelText(/Class head/));
  fireEvent.click(screen.getByRole('button', { name: 'Create staff login' }));
  await waitFor(() => expect(api.addStaff).toHaveBeenCalledWith('org', {
    name: 'Priya', email: 'priya@college.edu', department: 'Computer Science', degree: 'B.E.', year: '2nd year', section: 'A', class_head: true,
  }));
});

test('the staff list shows each class and lets the owner edit it', async () => {
  api.fetchStaff.mockResolvedValue([{ member_id: 'm1', user_id: 'u1', name: 'Priya', email: 'priya@college.edu', role: 'staff',
    has_signed_in: true, department: 'Computer Science', degree: 'B.E.', year: '2nd year', section: 'A', class_head: true }]);
  api.updateStaff.mockResolvedValue({ member_id: 'm1', department: 'Computer Science', degree: 'B.E.', year: '3rd year', section: 'A', class_head: true });
  render(<StaffPanel orgId="org" options={options} onToast={jest.fn()} />);
  expect(await screen.findByText('Computer Science · B.E. · 2nd year · Section A · Class head')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() => expect(api.updateStaff).toHaveBeenCalledWith('org', 'm1', expect.objectContaining({ year: '2nd year', class_head: true })));
});

test('clicking a staff name shows their students with each job readiness score', async () => {
  api.fetchStaff.mockResolvedValue([
    { member_id: 'm1', user_id: 'u1', name: 'Harini M', email: 'harini@college.edu', role: 'staff', has_signed_in: true, department: 'Computer Science', degree: '', year: '', section: '', class_head: false },
    { member_id: 'm0', user_id: 'u0', name: 'Owner', email: 'owner@college.edu', role: 'owner', has_signed_in: true },
  ]);
  const student = { member_id: 's1', user_id: 'l1', name: 'Ramya', email: 'ramya@gmail.com', role: 'member', external_id: null,
    joined_at: null, progress_shared: true, has_signed_in: true, department: 'Computer Science', year: '2nd year', section: 'A',
    last_active_at: null, staff_user_id: 'u1', readiness: { overall: 72.4, band: 'almost_ready', band_label: 'Almost ready', computed_at: '', areas: {} } };
  api.fetchFilteredMembers.mockResolvedValue([student] as never);
  const onOpenStudent = jest.fn();
  render(<StaffPanel orgId="org" options={options} onToast={jest.fn()} onOpenStudent={onOpenStudent} />);
  expect(screen.queryByRole('button', { name: 'Owner' })).not.toBeInTheDocument();     // only staff have students
  fireEvent.click(await screen.findByRole('button', { name: 'Harini M' }));
  await waitFor(() => expect(api.fetchFilteredMembers).toHaveBeenCalledWith('org', { staff: 'u1' }));
  expect(await screen.findByText('72 · Almost ready')).toBeInTheDocument();
  expect(screen.getByText('ring 72.4')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Ramya'));
  expect(onOpenStudent).toHaveBeenCalledWith(student);
});
