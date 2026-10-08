jest.mock('../../src/lib/learnerApi', () => ({
  acceptConsent: jest.fn(),
  saveLearnerProfile: jest.fn(),
}));

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import OnboardingScreen from '../../src/components/OnboardingScreen';
import * as api from '../../src/lib/learnerApi';
import type { LearnerSummary } from '../../src/lib/learnerApi';
import { parseMemberLines } from '../../src/lib/memberImport';

const mocked = jest.mocked(api);

function summary(overrides: Partial<LearnerSummary> = {}): LearnerSummary {
  return {
    profile: { target_role: '', degree: '', skills: [], experience: 'fresher', onboarding_completed: false, onboarding_completed_at: null },
    levels: [],
    level_choices: [],
    consent_required: false,
    membership: null,
    ...overrides,
  };
}

function fillProfile() {
  fireEvent.change(screen.getByPlaceholderText('e.g. Data Analyst'), { target: { value: 'Data Analyst' } });
  const skills = screen.getByPlaceholderText('Python, SQL, Excel…');
  fireEvent.change(skills, { target: { value: 'SQL, Python' } });
  fireEvent.keyDown(skills, { key: 'Enter' });
}

beforeEach(() => jest.clearAllMocks());

test('saves the target role, skills and experience', async () => {
  const done = summary({ profile: { ...summary().profile, onboarding_completed: true } });
  mocked.saveLearnerProfile.mockResolvedValue(done);
  const onDone = jest.fn();
  render(<OnboardingScreen name="Asha Rao" summary={summary()} onDone={onDone} onLogout={jest.fn()} />);
  expect(screen.getByText('Welcome, Asha')).toBeInTheDocument();
  fillProfile();
  expect(screen.getByText('SQL')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('radio', { name: 'Experienced' }));
  fireEvent.click(screen.getByRole('button', { name: 'Start learning' }));
  await waitFor(() => expect(onDone).toHaveBeenCalledWith(done));
  expect(mocked.saveLearnerProfile).toHaveBeenCalledWith({ target_role: 'Data Analyst', degree: '', skills: ['SQL', 'Python'], experience: 'experienced' });
  expect(mocked.acceptConsent).not.toHaveBeenCalled();
});

test('needs at least one skill', () => {
  render(<OnboardingScreen name="Asha" summary={summary()} onDone={jest.fn()} onLogout={jest.fn()} />);
  fireEvent.change(screen.getByPlaceholderText('e.g. Data Analyst'), { target: { value: 'Data Analyst' } });
  fireEvent.click(screen.getByRole('button', { name: 'Start learning' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Add at least one skill');
  expect(mocked.saveLearnerProfile).not.toHaveBeenCalled();
});

test('an account an organization created gives its own consent and sharing choice', async () => {
  const membership = {
    organization: { id: 'o1', name: 'ABC College', kind: 'college', member_limit: 1000, member_count: 10, created_at: null },
    role: 'member' as const, member_id: 'm1', external_id: '21CS001', progress_shared: false,
  };
  mocked.acceptConsent.mockResolvedValue(summary({ membership: { ...membership, progress_shared: true } }));
  mocked.saveLearnerProfile.mockResolvedValue(summary());
  render(<OnboardingScreen name="Asha" summary={summary({ consent_required: true, membership })} onDone={jest.fn()} onLogout={jest.fn()} />);
  expect(screen.getByText(/You were added by/)).toHaveTextContent('ABC College');
  fillProfile();
  const start = screen.getByRole('button', { name: 'Start learning' });
  expect(start).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox', { name: /I agree to the/ }));
  fireEvent.click(screen.getByRole('checkbox', { name: /Let ABC College see my job readiness/ }));
  fireEvent.click(start);
  await waitFor(() => expect(mocked.acceptConsent).toHaveBeenCalledWith(true));
  await waitFor(() => expect(mocked.saveLearnerProfile).toHaveBeenCalled());
});

test('bulk member lines: header skipped, any column order, roll number kept', () => {
  expect(parseMemberLines('name, email, roll\nPriya Kumar, priya@college.edu, 21CS001\narun@college.edu;Arun S\n\nno email here')).toEqual([
    { name: 'Priya Kumar', email: 'priya@college.edu', external_id: '21CS001' },
    { name: 'Arun S', email: 'arun@college.edu', external_id: undefined },
    { name: 'no email here', email: '', external_id: undefined },
  ]);
});
