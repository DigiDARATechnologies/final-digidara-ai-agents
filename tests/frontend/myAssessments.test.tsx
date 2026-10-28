jest.mock('../../src/lib/proctorApi', () => ({ fetchMyAssessments: jest.fn() }));

import { fireEvent, render, screen } from '@testing-library/react';
import MyAssessments from '../../src/components/MyAssessments';
import * as proctorApi from '../../src/lib/proctorApi';

const api = jest.mocked(proctorApi);
const item = (title: string, status: string, extra: object = {}) => ({
  id: title, title, kind: 'mock_interview', config: { round_type: 'technical', role_name: 'Data Analyst', num_questions: 5 },
  by: 'Priya', opens_at: null, closes_at: null, status, percent: null, path: `/assessment/tok-${title}`, ...extra,
});

test('learners not in an organization are asked to join first', async () => {
  api.fetchMyAssessments.mockResolvedValue({ member: false, organization: null, assessments: [] });
  const onJoin = jest.fn();
  render(<MyAssessments onOpen={jest.fn()} onJoin={onJoin} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Join with a code' }));
  expect(onJoin).toHaveBeenCalled();
});

test('open assessments start from here; submitted ones show the score', async () => {
  api.fetchMyAssessments.mockResolvedValue({ member: true, organization: 'Anna University', assessments: [
    item('Done test', 'submitted', { percent: 72 }), item('Round 1', 'open'), item('Next week', 'upcoming', { opens_at: '2026-11-04T10:00:00Z' }),
  ] } as never);
  const onOpen = jest.fn();
  render(<MyAssessments onOpen={onOpen} />);
  expect(await screen.findByText('Round 1')).toBeInTheDocument();
  expect(screen.getByText('72%')).toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: 'Start' })).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', { name: 'Start' }));
  expect(onOpen).toHaveBeenCalledWith('tok-Round 1');
  expect(screen.getByText(/Opens/)).toBeInTheDocument();
});
