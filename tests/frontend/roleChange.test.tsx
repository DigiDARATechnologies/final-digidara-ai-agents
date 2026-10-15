jest.mock('../../src/lib/learnerApi', () => ({
  LEVEL_IDS: ['beginner', 'medium', 'hard', 'professional'],
  LEVEL_LABELS: { beginner: 'Beginner', medium: 'Medium', hard: 'Hard', professional: 'Professional' },
  BAND_TONE: { not_started: 'muted', not_ready: 'low', developing: 'mid', almost_ready: 'good', job_ready: 'great' },
  fetchReadiness: jest.fn(),
  fetchReadinessHistory: jest.fn(),
  saveLearnerProfile: jest.fn(),
  setMyLevel: jest.fn(),
  setProgressSharing: jest.fn(),
  suggestRoleSkills: jest.fn(),
}));
jest.mock('../../src/lib/jobFetchFlow', () => ({ syncJobProfileWithGoal: jest.fn() }));
jest.mock('../../src/components/CareerPlanPanel', () => () => null);
jest.mock('../../src/components/MemoryPanel', () => () => null);

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ReadinessView from '../../src/components/ReadinessView';
import * as api from '../../src/lib/learnerApi';
import * as jobs from '../../src/lib/jobFetchFlow';
import type { LearnerSummary, Readiness } from '../../src/lib/learnerApi';

const mocked = jest.mocked(api);

function summary(role: string, history: LearnerSummary['role_history'] = []): LearnerSummary {
  return {
    profile: { target_role: role, degree: 'm.sc', skills: ['python'], experience: 'fresher', onboarding_completed: true, onboarding_completed_at: null },
    levels: [], level_choices: [], consent_required: false, membership: null, role_history: history,
  };
}

const readiness = {
  overall: null, band: 'not_started', band_label: 'Not started', coverage: { assessed: 0, total: 7 },
  areas: [], next_steps: [], profile: summary('ai engineer').profile, computed_at: '2026-10-12T10:00:00',
} as unknown as Readiness;

beforeEach(() => {
  jest.clearAllMocks();
  mocked.fetchReadiness.mockResolvedValue(readiness);
  mocked.fetchReadinessHistory.mockResolvedValue([]);
});

async function openEditor(current: LearnerSummary) {
  const onToast = jest.fn();
  render(<ReadinessView summary={current} onSummaryChange={jest.fn()} onBack={jest.fn()} onToast={onToast} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Edit profile' }));
  return onToast;
}

test('a new target role asks first, then starts every level from zero', async () => {
  mocked.saveLearnerProfile.mockResolvedValue(summary('data scientist'));
  const onToast = await openEditor(summary('ai engineer'));
  fireEvent.change(screen.getByPlaceholderText('e.g. data analyst'), { target: { value: 'Data Scientist' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save profile' }));
  const dialog = await screen.findByRole('alertdialog');
  expect(dialog).toHaveTextContent('Every agent\'s level goes back to Beginner');
  expect(dialog).toHaveTextContent('Your progress for ai engineer is kept');
  expect(mocked.saveLearnerProfile).not.toHaveBeenCalled();
  // The new role's skills are asked for, starting from the usual ones for it.
  expect(dialog).toHaveTextContent('Skills for data scientist');
  expect(dialog).toHaveTextContent('statistics');
  fireEvent.click(screen.getByRole('button', { name: 'Remove statistics' }));
  // A current skill removed from the list can be kept again with one tap.
  fireEvent.click(screen.getByRole('button', { name: 'Remove python' }));
  fireEvent.click(screen.getByRole('button', { name: '+ python' }));
  fireEvent.click(screen.getByRole('button', { name: 'Yes, change role' }));
  await waitFor(() => expect(mocked.saveLearnerProfile).toHaveBeenCalled());
  const saved = mocked.saveLearnerProfile.mock.calls[0][0];
  expect(saved.target_role).toBe('data scientist');
  expect(saved.skills).toContain('pandas');
  expect(saved.skills).toContain('python');
  expect(saved.skills).not.toContain('statistics');
  expect(mocked.suggestRoleSkills).not.toHaveBeenCalled();
  expect(jobs.syncJobProfileWithGoal).toHaveBeenCalled();
  await waitFor(() => expect(onToast).toHaveBeenCalledWith(expect.stringContaining('starts from zero')));
});

test('a role worked on before says its levels come back, with its own skills', async () => {
  await openEditor(summary('ai engineer', [{ role: 'data scientist', skills: ['r', 'tableau'], levels: { aptitude_agent: 'medium' } }]));
  fireEvent.change(screen.getByPlaceholderText('e.g. data analyst'), { target: { value: 'data scientist' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save profile' }));
  const dialog = await screen.findByRole('alertdialog');
  expect(dialog).toHaveTextContent('its levels and points come back');
  expect(dialog).toHaveTextContent('Your skills from last time');
  expect(screen.getByRole('button', { name: 'Remove tableau' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  expect(mocked.saveLearnerProfile).not.toHaveBeenCalled();
});

test('the same role in other letters saves without asking', async () => {
  mocked.saveLearnerProfile.mockResolvedValue(summary('ai engineer'));
  await openEditor(summary('AI Engineer'));
  fireEvent.click(screen.getByRole('button', { name: 'Save profile' }));
  await waitFor(() => expect(mocked.saveLearnerProfile).toHaveBeenCalled());
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
});

test('any other role gets suggested skills, and saving needs at least one', async () => {
  mocked.suggestRoleSkills.mockResolvedValue(['Solidity', 'smart contracts']);
  mocked.saveLearnerProfile.mockResolvedValue(summary('blockchain developer'));
  await openEditor(summary('ai engineer'));
  fireEvent.change(screen.getByPlaceholderText('e.g. data analyst'), { target: { value: 'blockchain developer' } });
  expect(screen.getByText(/you'll choose the skills for it/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Save profile' }));
  expect(await screen.findByRole('button', { name: 'Remove solidity' })).toBeInTheDocument();
  expect(mocked.suggestRoleSkills).toHaveBeenCalledWith('blockchain developer');
  fireEvent.click(screen.getByRole('button', { name: 'Remove solidity' }));
  fireEvent.click(screen.getByRole('button', { name: 'Remove smart contracts' }));
  fireEvent.click(screen.getByRole('button', { name: 'Yes, change role' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Add at least one skill for blockchain developer');
  expect(mocked.saveLearnerProfile).not.toHaveBeenCalled();
});

test('a learner with two roles can switch between them from the readiness page', async () => {
  const history = [
    { role: 'ai engineer', skills: ['python'], levels: {} },
    { role: 'data analyst', skills: ['sql', 'excel'], levels: { mock_interview: 'medium' as const } },
  ];
  mocked.saveLearnerProfile.mockResolvedValue(summary('data analyst', history));
  render(<ReadinessView summary={summary('ai engineer', history)} onSummaryChange={jest.fn()} onBack={jest.fn()} onToast={jest.fn()} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Switch role (2)' }));
  const picker = screen.getByRole('dialog', { name: 'Switch role' });
  expect(picker).toHaveTextContent('Current role');
  expect(picker).toHaveTextContent('sql, excel · 1 level above Beginner');
  fireEvent.click(screen.getByRole('button', { name: 'Switch' }));
  const dialog = await screen.findByRole('alertdialog');
  expect(dialog).toHaveTextContent('its levels and points come back');
  fireEvent.click(screen.getByRole('button', { name: 'Yes, change role' }));
  await waitFor(() => expect(mocked.saveLearnerProfile).toHaveBeenCalledWith(
    { target_role: 'data analyst', degree: 'm.sc', skills: ['sql', 'excel'], experience: 'fresher' }));
});

test('no switch button with only one role', async () => {
  render(<ReadinessView summary={summary('ai engineer', [{ role: 'ai engineer', levels: {} }])} onSummaryChange={jest.fn()} onBack={jest.fn()} onToast={jest.fn()} />);
  await screen.findByRole('button', { name: 'Edit profile' });
  expect(screen.queryByRole('button', { name: /Switch role/ })).toBeNull();
});
