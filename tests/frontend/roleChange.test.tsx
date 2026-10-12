jest.mock('../../src/lib/learnerApi', () => ({
  LEVEL_IDS: ['beginner', 'medium', 'hard', 'professional'],
  LEVEL_LABELS: { beginner: 'Beginner', medium: 'Medium', hard: 'Hard', professional: 'Professional' },
  BAND_TONE: { not_started: 'muted', not_ready: 'low', developing: 'mid', almost_ready: 'good', job_ready: 'great' },
  fetchReadiness: jest.fn(),
  fetchReadinessHistory: jest.fn(),
  saveLearnerProfile: jest.fn(),
  setMyLevel: jest.fn(),
  setProgressSharing: jest.fn(),
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
  fireEvent.click(screen.getByRole('button', { name: 'Yes, change role' }));
  await waitFor(() => expect(mocked.saveLearnerProfile).toHaveBeenCalledWith(expect.objectContaining({ target_role: 'data scientist' })));
  expect(jobs.syncJobProfileWithGoal).toHaveBeenCalled();
  await waitFor(() => expect(onToast).toHaveBeenCalledWith(expect.stringContaining('starts from zero')));
});

test('a role worked on before says its levels come back', async () => {
  await openEditor(summary('ai engineer', [{ role: 'data scientist', levels: { aptitude_agent: 'medium' } }]));
  fireEvent.change(screen.getByPlaceholderText('e.g. data analyst'), { target: { value: 'data scientist' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save profile' }));
  expect(await screen.findByRole('alertdialog')).toHaveTextContent('its levels and points come back');
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
