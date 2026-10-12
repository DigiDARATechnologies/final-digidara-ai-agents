jest.mock('../../src/lib/orgApi', () => ({
  CLASS_KINDS: ['department', 'year', 'section'],
  CLASS_LABELS: { department: 'Department', year: 'Year', section: 'Section' },
  previewJoinCode: jest.fn(),
  joinWithClass: jest.fn(),
}));
jest.mock('../../src/lib/learnerApi', () => ({ fetchLearnerSummary: jest.fn() }));

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import JoinOrganization from '../../src/components/org/JoinOrganization';
import * as orgApi from '../../src/lib/orgApi';
import * as learnerApi from '../../src/lib/learnerApi';

const org = jest.mocked(orgApi);
const learner = jest.mocked(learnerApi);
const options = { department: ['CSE'], year: ['1st year', '2nd year'], section: ['A', 'B'] };
const membership = { organization: { id: 'o1', name: 'Anna University', kind: 'college', member_limit: 1000, member_count: 3, created_at: null },
  role: 'member' as const, member_id: 'm1', external_id: null, progress_shared: true };

beforeEach(() => {
  jest.clearAllMocks();
  org.joinWithClass.mockResolvedValue({ membership: null });
  learner.fetchLearnerSummary.mockResolvedValue({ profile: {} as never, levels: [], level_choices: [], consent_required: false, membership });
});

function typeCode(code: string) {
  fireEvent.change(screen.getByPlaceholderText('ABCD2345'), { target: { value: code } });
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
}

test('a class code shows the class it places the learner in, and the consent', async () => {
  org.previewJoinCode.mockResolvedValue({ organization: { name: 'Anna University', kind: 'college' },
    code: { label: 'M.Sc CS · 1st year · A', department: 'M.Sc CS', year: '1st year', section: 'A' }, options });
  const onJoined = jest.fn();
  render(<JoinOrganization onJoined={onJoined} onToast={jest.fn()} />);
  typeCode('abcd2345');
  expect(await screen.findByText('M.Sc CS')).toBeInTheDocument();
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  expect(screen.getByText(/admins can see your job readiness, levels, activity in every agent and your chats/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Join Anna University' }));
  await waitFor(() => expect(onJoined).toHaveBeenCalledWith(membership));
  expect(org.joinWithClass).toHaveBeenCalledWith('ABCD2345', {});
});

test('a general code lets the learner pick, or add a new department', async () => {
  org.previewJoinCode.mockResolvedValue({ organization: { name: 'Anna University', kind: 'college' },
    code: { label: 'General', department: null, year: null, section: null }, options });
  render(<JoinOrganization onJoined={jest.fn()} onToast={jest.fn()} />);
  typeCode('GEN12345');
  const [department, year] = await screen.findAllByRole('combobox');
  fireEvent.change(department, { target: { value: '__add_new__' } });
  fireEvent.change(screen.getByPlaceholderText('New department'), { target: { value: '  M.Sc   Data Science ' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add' }));
  fireEvent.change(year, { target: { value: '2nd year' } });
  fireEvent.click(screen.getByRole('button', { name: 'Join Anna University' }));
  await waitFor(() => expect(org.joinWithClass).toHaveBeenCalledWith('GEN12345', { department: 'M.Sc Data Science', year: '2nd year' }));
});

test('an unknown code shows why', async () => {
  org.previewJoinCode.mockRejectedValue(new Error('No organization has that join code.'));
  render(<JoinOrganization onJoined={jest.fn()} onToast={jest.fn()} />);
  typeCode('ZZZZ9999');
  expect(await screen.findByRole('alert')).toHaveTextContent('No organization has that join code.');
});
